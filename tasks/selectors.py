"""
Every read query for tasks (spec §12). §6's list endpoint parameters and the
§3.3 "overdue is never a stored column" rule both live here.
"""

from django.db import connection
from django.db.models import BooleanField, Case, Q, When
from django.utils import timezone

from .models import Task

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
