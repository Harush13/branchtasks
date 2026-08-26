"""
Phase 6 gate (spec §8): the four headline counters, the breakdown shapes,
and the needs-attention ordering — exercised directly against
tasks/selectors.py, independent of the API/HTML layers on top of it.
"""

import datetime

import pytest
from django.utils import timezone

from tasks.models import Task
from tasks.selectors import dashboard_breakdown, dashboard_counters, needs_attention

pytestmark = pytest.mark.django_db


def _make_task(*, branch, category, opener, **kwargs):
    kwargs.setdefault("title", "t")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


class TestDashboardCounters:
    def test_counts_open_closed_overdue_urgent(self, branch, category, opener, member):
        today = timezone.localdate()
        _make_task(branch=branch, category=category, opener=opener, status=Task.Status.NEW)
        done = _make_task(branch=branch, category=category, opener=opener)
        done.status = Task.Status.DONE
        done.completed_at = timezone.now()
        done.save()
        _make_task(
            branch=branch,
            category=category,
            opener=opener,
            due_date=today - datetime.timedelta(days=1),
        )
        _make_task(branch=branch, category=category, opener=opener, priority=Task.Priority.URGENT)

        counts = dashboard_counters()

        assert counts["open"] == 3  # new + overdue-active + urgent-active
        assert counts["closed"] == 1
        assert counts["overdue"] == 1
        assert counts["urgent"] == 1

    def test_cancelled_never_counted_open_or_closed(self, branch, category, opener):
        cancelled = _make_task(branch=branch, category=category, opener=opener)
        cancelled.status = Task.Status.CANCELLED
        cancelled.cancelled_at = timezone.now()
        cancelled.save()

        counts = dashboard_counters()

        assert counts["open"] == 0
        assert counts["closed"] == 0


class TestDashboardBreakdown:
    def test_by_branch_groups_active_tasks_by_status(self, branch, category, opener):
        _make_task(branch=branch, category=category, opener=opener, status=Task.Status.NEW)
        _make_task(branch=branch, category=category, opener=opener, status=Task.Status.IN_PROGRESS)
        done = _make_task(branch=branch, category=category, opener=opener)
        done.status = Task.Status.DONE
        done.completed_at = timezone.now()
        done.save()

        rows = dashboard_breakdown("branch")

        by_status = {r["status"]: r["n"] for r in rows if r["group"] == branch.name_he}
        assert by_status == {"new": 1, "in_progress": 1}  # done excluded (inactive)

    def test_by_status_includes_closed_tasks(self, branch, category, opener):
        done = _make_task(branch=branch, category=category, opener=opener)
        done.status = Task.Status.DONE
        done.completed_at = timezone.now()
        done.save()

        rows = dashboard_breakdown("status")

        assert {"status": "done", "n": 1} in rows

    def test_by_assignee_reports_open_and_overdue(self, branch, category, opener, member):
        today = timezone.localdate()
        _make_task(branch=branch, category=category, opener=opener, assignee=member)
        _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=3),
        )

        rows = dashboard_breakdown("assignee")

        row = next(r for r in rows if r["assignee"] == member.full_name)
        assert row["open_tasks"] == 2
        assert row["overdue"] == 1

    def test_unknown_dimension_raises(self):
        with pytest.raises(ValueError):
            dashboard_breakdown("nonsense")


class TestNeedsAttention:
    def test_sorted_by_days_late_descending(self, branch, category, opener, member):
        today = timezone.localdate()
        slightly_late = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=1),
        )
        very_late = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=10),
        )
        urgent_not_overdue = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            priority=Task.Priority.URGENT,
        )

        result = needs_attention()

        assert [t.pk for t in result] == [very_late.pk, slightly_late.pk, urgent_not_overdue.pk]
        assert result[0].days_late == 10
        assert result[2].days_late == 0

    def test_excludes_done_and_low_priority_on_time_tasks(self, branch, category, opener):
        done_but_would_be_overdue = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            due_date=timezone.localdate() - datetime.timedelta(days=5),
        )
        done_but_would_be_overdue.status = Task.Status.DONE
        done_but_would_be_overdue.completed_at = timezone.now()
        done_but_would_be_overdue.save()
        _make_task(branch=branch, category=category, opener=opener)  # on-time, normal priority

        assert needs_attention() == []
