"""
Phase 7 gate (spec §9): the four KPI queries, with special attention to the
"critical rule" the spec calls out explicitly — cancelled tasks must never
appear in the numerator or denominator of a closure metric.
"""

import datetime

import pytest
from django.utils import timezone

from tasks.models import Task
from tasks.selectors import (
    kpi_avg_days_to_close,
    kpi_on_time_closure_rate,
    kpi_opened_vs_closed_by_month,
    kpi_performance_by_branch,
)

pytestmark = pytest.mark.django_db


def _close(task, *, days_to_close, on_time=True):
    task.status = Task.Status.DONE
    task.completed_at = task.created_at + datetime.timedelta(days=days_to_close)
    if task.due_date is None:
        task.due_date = timezone.localdate() + (
            datetime.timedelta(days=days_to_close) if on_time else -datetime.timedelta(days=1)
        )
    task.save()
    return task


def _cancel(task):
    task.status = Task.Status.CANCELLED
    task.cancelled_at = timezone.now()
    task.save()
    return task


class TestAvgDaysToClose:
    def test_averages_only_recent_closures(self, branch, category, opener):
        recent = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(recent, days_to_close=4)

        old = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(old, days_to_close=10)
        old.completed_at = timezone.now() - datetime.timedelta(days=200)
        old.save()

        assert kpi_avg_days_to_close(90) == 4.0

    def test_none_when_nothing_closed(self, branch, category, opener):
        Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        assert kpi_avg_days_to_close(90) is None

    def test_cancelled_tasks_excluded(self, branch, category, opener):
        cancelled = Task.objects.create(
            title="t", branch=branch, category=category, opened_by=opener
        )
        _cancel(cancelled)
        assert kpi_avg_days_to_close(90) is None


class TestOnTimeClosureRate:
    def test_rate_over_done_tasks_with_a_due_date(self, branch, category, opener):
        on_time = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(on_time, days_to_close=1, on_time=True)
        late = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(late, days_to_close=1, on_time=False)

        assert kpi_on_time_closure_rate() == 50.0

    def test_done_without_due_date_excluded(self, branch, category, opener):
        done_no_due = Task.objects.create(
            title="t", branch=branch, category=category, opened_by=opener
        )
        done_no_due.status = Task.Status.DONE
        done_no_due.completed_at = timezone.now()
        done_no_due.save()

        assert kpi_on_time_closure_rate() is None

    def test_cancelled_excluded_from_numerator_and_denominator(self, branch, category, opener):
        on_time = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(on_time, days_to_close=1, on_time=True)
        cancelled = Task.objects.create(
            title="t",
            branch=branch,
            category=category,
            opened_by=opener,
            due_date=timezone.localdate(),
        )
        _cancel(cancelled)

        assert kpi_on_time_closure_rate() == 100.0


class TestPerformanceByBranch:
    def test_closed_excludes_cancelled_open_excludes_done(self, branch, category, opener):
        closed = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(closed, days_to_close=2)
        cancelled = Task.objects.create(
            title="t", branch=branch, category=category, opened_by=opener
        )
        _cancel(cancelled)
        Task.objects.create(
            title="t", branch=branch, category=category, opened_by=opener, status=Task.Status.NEW
        )

        row = next(r for r in kpi_performance_by_branch() if r["branch"] == branch.name_he)

        assert row["closed"] == 1
        assert row["open"] == 1
        assert row["avg_days"] == 2.0


class TestOpenedVsClosedByMonth:
    def test_closed_counts_cohort_now_done(self, branch, category, opener):
        task = Task.objects.create(title="t", branch=branch, category=category, opened_by=opener)
        _close(task, days_to_close=1)

        rows = kpi_opened_vs_closed_by_month(12)

        this_month = timezone.localdate().replace(day=1).isoformat()
        row = next(r for r in rows if r["month"] == this_month)
        assert row["opened"] == 1
        assert row["closed"] == 1
