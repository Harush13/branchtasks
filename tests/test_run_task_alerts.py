"""
Phase 5 gate (spec §7 + §13): `run_task_alerts` sends due_soon/overdue alerts
and is idempotent — running it twice must not double the notification count.
"""

import datetime

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from notifications.models import Notification
from tasks.models import Task

pytestmark = pytest.mark.django_db


def _make_task(*, branch, category, opener, assignee, due_date, status=Task.Status.IN_PROGRESS):
    task = Task.objects.create(
        title="t",
        branch=branch,
        category=category,
        opened_by=opener,
        assignee=assignee,
        due_date=due_date,
        status=status,
    )
    return task


class TestRunTaskAlerts:
    def test_due_soon_notifies_assignee_only(self, branch, category, opener, member, manager):
        today = timezone.localdate()
        task = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today + datetime.timedelta(days=2),
        )

        call_command("run_task_alerts")

        assert Notification.objects.filter(
            task=task, user=member, kind=Notification.Kind.DUE_SOON
        ).exists()
        assert not Notification.objects.filter(
            task=task, user=manager, kind=Notification.Kind.DUE_SOON
        ).exists()

    def test_overdue_notifies_assignee_and_managers(
        self, branch, category, opener, member, manager
    ):
        today = timezone.localdate()
        task = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=1),
        )

        call_command("run_task_alerts")

        assert Notification.objects.filter(
            task=task, user=member, kind=Notification.Kind.OVERDUE
        ).exists()
        assert Notification.objects.filter(
            task=task, user=manager, kind=Notification.Kind.OVERDUE
        ).exists()

    def test_done_and_cancelled_tasks_are_never_alerted(self, branch, category, opener, member):
        today = timezone.localdate()
        done = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=1),
        )
        done.status = Task.Status.DONE
        done.completed_at = timezone.now()
        done.save()
        cancelled = _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=1),
        )
        cancelled.status = Task.Status.CANCELLED
        cancelled.cancelled_at = timezone.now()
        cancelled.save()

        call_command("run_task_alerts")

        assert not Notification.objects.filter(kind=Notification.Kind.OVERDUE).exists()

    def test_running_twice_is_idempotent(self, branch, category, opener, member, manager):
        today = timezone.localdate()
        _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today - datetime.timedelta(days=1),
        )

        call_command("run_task_alerts")
        first_count = Notification.objects.count()
        call_command("run_task_alerts")
        second_count = Notification.objects.count()

        assert first_count > 0
        assert first_count == second_count

    @override_settings(EMAIL_ENABLED=True)
    def test_email_sent_when_enabled(self, branch, category, opener, member):
        member.email = "member1@example.com"
        member.save(update_fields=["email"])
        today = timezone.localdate()
        _make_task(
            branch=branch,
            category=category,
            opener=opener,
            assignee=member,
            due_date=today + datetime.timedelta(days=2),
        )

        call_command("run_task_alerts")

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["member1@example.com"]
