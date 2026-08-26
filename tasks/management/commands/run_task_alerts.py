"""
Spec §7's daily scheduled job. Invoked by cron, not Celery (see spec §2 —
no broker in v1):

    0 7 * * * cd /path/to/branchtasks && python manage.py run_task_alerts

Runs at 07:00 in TIME_ZONE (Asia/Jerusalem, see config/settings/base.py), so
the cron entry above must live in a crontab already set to that zone (or be
adjusted to the host's zone before deploy).

Idempotent by construction: every notification goes through
`notifications.services.notify()`, which is a `get_or_create` on the
UNIQUE(task, user, kind) constraint. Running this command twice in the same
day is a no-op the second time — see tests/test_run_task_alerts.py.
"""

from django.core.management.base import BaseCommand

from accounts.models import User
from accounts.permissions import is_manager
from notifications.models import Notification
from notifications.services import notify
from tasks.selectors import tasks_due_soon, tasks_overdue


class Command(BaseCommand):
    help = "Send due_soon and overdue task alerts (spec §7). Run daily at 07:00 Asia/Jerusalem."

    def handle(self, *args, **options):
        due_soon_count = self._notify_due_soon()
        overdue_count = self._notify_overdue()
        self.stdout.write(
            self.style.SUCCESS(
                f"run_task_alerts: {due_soon_count} due_soon, {overdue_count} overdue notice(s)."
            )
        )

    def _notify_due_soon(self):
        """§7: tasks due in exactly 2 days and still active → notify assignee only."""
        count = 0
        for task in tasks_due_soon(days=2).filter(assignee__isnull=False):
            notify(
                task,
                task.assignee,
                Notification.Kind.DUE_SOON,
                f"{task.ref} is due in 2 days: {task.title}",
            )
            count += 1
        return count

    def _notify_overdue(self):
        """§7: tasks past due and still active → notify assignee and every manager/admin."""
        managers = [u for u in User.objects.filter(is_active=True) if is_manager(u)]
        count = 0
        for task in tasks_overdue():
            recipients = set(managers)
            if task.assignee_id:
                recipients.add(task.assignee)
            for user in recipients:
                notify(
                    task,
                    user,
                    Notification.Kind.OVERDUE,
                    f"{task.ref} is overdue: {task.title}",
                )
                count += 1
        return count
