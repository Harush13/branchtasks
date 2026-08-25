import datetime

import pytest
from django.utils import timezone

from tasks.models import Task
from tasks.selectors import annotate_overdue, filter_tasks, order_tasks, task_queryset

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


class TestOverdueAnnotation:
    def test_past_due_open_task_is_overdue(self, branch, category, opener):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        task = make_task(branch, category, opener, due_date=yesterday)
        qs = annotate_overdue(task_queryset().filter(pk=task.pk))
        assert qs.get().overdue is True

    def test_due_today_is_not_overdue(self, branch, category, opener):
        today = timezone.localdate()
        task = make_task(branch, category, opener, due_date=today)
        qs = annotate_overdue(task_queryset().filter(pk=task.pk))
        assert qs.get().overdue is False

    def test_due_tomorrow_is_not_overdue(self, branch, category, opener):
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        task = make_task(branch, category, opener, due_date=tomorrow)
        qs = annotate_overdue(task_queryset().filter(pk=task.pk))
        assert qs.get().overdue is False

    def test_past_due_but_done_is_not_overdue(self, branch, category, opener):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        task = make_task(
            branch,
            category,
            opener,
            due_date=yesterday,
            status=Task.Status.DONE,
            completed_at=timezone.now(),
        )
        qs = annotate_overdue(task_queryset().filter(pk=task.pk))
        assert qs.get().overdue is False

    def test_no_due_date_is_not_overdue(self, branch, category, opener):
        task = make_task(branch, category, opener)
        qs = annotate_overdue(task_queryset().filter(pk=task.pk))
        assert qs.get().overdue is False


class TestFilterTasks:
    def test_filter_by_status(self, branch, category, opener):
        make_task(branch, category, opener, status=Task.Status.NEW)
        make_task(branch, category, opener, status=Task.Status.IN_PROGRESS)
        qs = filter_tasks(task_queryset(), status=[Task.Status.IN_PROGRESS])
        assert qs.count() == 1
        assert qs.first().status == Task.Status.IN_PROGRESS

    def test_filter_by_priority_min(self, branch, category, opener):
        make_task(branch, category, opener, priority=Task.Priority.LOW)
        high = make_task(branch, category, opener, priority=Task.Priority.HIGH)
        qs = filter_tasks(task_queryset(), priority_min=Task.Priority.HIGH)
        assert list(qs) == [high]

    def test_filter_overdue_flag(self, branch, category, opener):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        overdue_task = make_task(branch, category, opener, due_date=yesterday)
        make_task(
            branch, category, opener, due_date=timezone.localdate() + datetime.timedelta(days=5)
        )
        qs = filter_tasks(task_queryset(), overdue=True)
        assert list(qs) == [overdue_task]

    def test_filter_by_free_text_q(self, branch, category, opener):
        make_task(branch, category, opener, title="Fix the printer")
        make_task(branch, category, opener, title="Order supplies")
        qs = filter_tasks(task_queryset(), q="printer")
        assert qs.count() == 1


class TestOrderTasks:
    def test_default_ordering_is_priority_desc_then_due_date_asc(self, branch, category, opener):
        low = make_task(
            branch, category, opener, priority=Task.Priority.LOW, due_date=timezone.localdate()
        )
        urgent = make_task(
            branch, category, opener, priority=Task.Priority.URGENT, due_date=timezone.localdate()
        )
        normal = make_task(
            branch, category, opener, priority=Task.Priority.NORMAL, due_date=timezone.localdate()
        )
        ordered = list(order_tasks(task_queryset().filter(pk__in=[low.pk, urgent.pk, normal.pk])))
        assert ordered == [urgent, normal, low]
