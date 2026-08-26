"""
Every read query for tasks (spec §12). §6's list endpoint parameters and the
§3.3 "overdue is never a stored column" rule both live here.
"""

import datetime

from django.db import connection
from django.db.models import BooleanField, Case, Count, Q, When
from django.utils import timezone

from .models import Task

# §8's breakdown dimensions that group by branch/category/priority, each
# alongside status — same query shape, only the grouping field differs.
# `assignee` and `status` get their own shape below and are not in this map.
_BREAKDOWN_FIELDS = {
    "branch": "branch__name_he",
    "category": "category__name_he",
    "priority": "priority",
}

_INACTIVE_STATUSES = [Task.Status.DONE, Task.Status.CANCELLED]

# §6 default ordering: priority desc, due_date asc.
DEFAULT_ORDERING = ("-priority", "due_date")


def task_queryset():
    """Base queryset for every task list — always select_related to avoid
    the N+1 the spec explicitly calls out."""
    return Task.objects.select_related("branch", "category", "assignee", "opened_by")


def annotate_overdue(qs):
    """
    §3.3: overdue is computed, never stored — `due_date < today AND status
    NOT IN ('done','cancelled')`. A stored flag would go stale at midnight.
    """
    today = timezone.localdate()
    return qs.annotate(
        overdue=Case(
            When(
                Q(due_date__lt=today) & ~Q(status__in=_INACTIVE_STATUSES),
                then=True,
            ),
            default=False,
            output_field=BooleanField(),
        )
    )


def filter_tasks(
    qs,
    *,
    branch=None,
    category=None,
    status=None,
    assignee=None,
    opened_by=None,
    priority_min=None,
    overdue=None,
    due_before=None,
    due_after=None,
    q=None,
):
    """Covers every §6 GET /api/tasks query parameter."""
    if branch is not None:
        qs = qs.filter(branch=branch)
    if category is not None:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status__in=status if isinstance(status, (list, tuple)) else [status])
    if assignee is not None:
        qs = qs.filter(assignee=assignee)
    if opened_by is not None:
        qs = qs.filter(opened_by=opened_by)
    if priority_min is not None:
        qs = qs.filter(priority__gte=priority_min)
    if overdue:
        today = timezone.localdate()
        qs = qs.filter(due_date__lt=today).exclude(status__in=_INACTIVE_STATUSES)
    if due_before is not None:
        qs = qs.filter(due_date__lt=due_before)
    if due_after is not None:
        qs = qs.filter(due_date__gt=due_after)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    return qs


def tasks_due_soon(days=2):
    """§7 scheduled job: active tasks due in exactly `days` days."""
    target = timezone.localdate() + datetime.timedelta(days=days)
    return task_queryset().filter(due_date=target).exclude(status__in=_INACTIVE_STATUSES)


def tasks_overdue():
    """§7 scheduled job: active tasks already past their due date."""
    today = timezone.localdate()
    return task_queryset().filter(due_date__lt=today).exclude(status__in=_INACTIVE_STATUSES)


def dashboard_counters():
    """§8's four headline counters, one aggregate query."""
    today = timezone.localdate()
    active = ~Q(status__in=_INACTIVE_STATUSES)
    return Task.objects.aggregate(
        open=Count("id", filter=active),
        closed=Count("id", filter=Q(status=Task.Status.DONE)),
        overdue=Count("id", filter=active & Q(due_date__lt=today)),
        urgent=Count("id", filter=active & Q(priority=Task.Priority.URGENT)),
    )


def dashboard_breakdown(by):
    """
    §8's breakdown endpoint. `branch`/`category`/`priority` share one shape
    (dimension x status, active tasks only, for a stacked chart);
    `status` and `assignee` each need their own shape, so they're not in
    `_BREAKDOWN_FIELDS`. Raises ValueError on an unknown `by` — the view
    turns that into a 400.
    """
    if by == "status":
        return _breakdown_by_status()
    if by == "assignee":
        return _breakdown_by_assignee()
    if by not in _BREAKDOWN_FIELDS:
        raise ValueError(f"Unknown breakdown dimension: {by!r}")
    field = _BREAKDOWN_FIELDS[by]
    rows = (
        Task.objects.exclude(status__in=_INACTIVE_STATUSES)
        .values(field, "status")
        .annotate(n=Count("id"))
        .order_by(field, "status")
    )
    return [{"group": row[field], "status": row["status"], "n": row["n"]} for row in rows]


def _breakdown_by_status():
    """Whole-table status distribution — includes done/cancelled, since
    that's the point of a status-distribution chart."""
    rows = Task.objects.values("status").annotate(n=Count("id")).order_by("status")
    return [{"status": row["status"], "n": row["n"]} for row in rows]


def _breakdown_by_assignee():
    """§8's 'load by assignee': open_tasks + overdue per person, busiest first."""
    today = timezone.localdate()
    rows = (
        Task.objects.exclude(status__in=_INACTIVE_STATUSES)
        .filter(assignee__isnull=False)
        .values("assignee__full_name")
        .annotate(
            open_tasks=Count("id"),
            overdue=Count("id", filter=Q(due_date__lt=today)),
        )
        .order_by("-open_tasks")
    )
    return [
        {
            "assignee": row["assignee__full_name"],
            "open_tasks": row["open_tasks"],
            "overdue": row["overdue"],
        }
        for row in rows
    ]


def needs_attention():
    """
    §8's live table: every active task that's Urgent OR overdue, sorted by
    days-late descending. Day-count arithmetic is done in Python rather
    than with ORM date-diff functions (portability isolated the same way
    order_by_hebrew_name isolates its Postgres-only feature) — the result
    set here is small by definition, so there's no N+1/perf concern.
    """
    today = timezone.localdate()
    qs = (
        annotate_overdue(task_queryset())
        .exclude(status__in=_INACTIVE_STATUSES)
        .filter(Q(priority=Task.Priority.URGENT) | Q(due_date__lt=today))
    )

    def days_late(task):
        return (today - task.due_date).days if task.due_date and task.due_date < today else 0

    tasks = list(qs)
    for task in tasks:
        task.days_late = days_late(task)
    tasks.sort(key=lambda t: t.days_late, reverse=True)
    return tasks


def order_tasks(qs, ordering=None):
    if ordering:
        fields = ordering if isinstance(ordering, (list, tuple)) else [ordering]
        return qs.order_by(*fields)
    return qs.order_by(*DEFAULT_ORDERING)


def order_by_hebrew_name(qs, field):
    """
    §10.4: sort by Hebrew collation on Postgres (he-IL-x-icu). SQLite has no
    ICU collation support, so dev falls back to plain ordering — the one
    genuinely non-portable feature, isolated here and re-verified at Phase 7.
    """
    if connection.vendor == "postgresql":
        from django.db.models.functions import Collate

        return qs.annotate(_sort_key=Collate(field, "he-IL-x-icu")).order_by("_sort_key")
    return qs.order_by(field)
