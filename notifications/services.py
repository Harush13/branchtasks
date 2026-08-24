"""
Immediate notification triggers (spec §7, synchronous half). The scheduled
`run_task_alerts` job (due_soon/overdue) is Phase 5 — this module only covers
the three triggers that fire inline from tasks/services.py.
"""

from accounts.models import User
from accounts.permissions import is_manager

from .models import Notification


def notify(task, user, kind, body):
    """
    Wraps get_or_create on the UNIQUE(task, user, kind) constraint so a
    duplicate trigger (e.g. reassigning back to the same person) is a no-op
    instead of an IntegrityError. First notice for a given (task, user,
    kind) wins; body is not updated on repeat.
    """
    Notification.objects.get_or_create(task=task, user=user, kind=kind, defaults={"body": body})


def notify_assigned(task, actor):
    if task.assignee_id and task.assignee_id != actor.id:
        notify(
            task,
            task.assignee,
            Notification.Kind.ASSIGNED,
            f"You were assigned to {task.ref}: {task.title}",
        )


def notify_reassigned(task, actor):
    if task.assignee_id and task.assignee_id != actor.id:
        notify(
            task,
            task.assignee,
            Notification.Kind.REASSIGNED,
            f"You were reassigned to {task.ref}: {task.title}",
        )


def notify_urgent(task, actor):
    """§7: priority set to Urgent notifies the assignee plus every manager/admin."""
    recipients = set()
    if task.assignee_id:
        recipients.add(task.assignee)
    recipients.update(u for u in User.objects.filter(is_active=True) if is_manager(u))
    recipients.discard(actor)
    for user in recipients:
        notify(
            task,
            user,
            Notification.Kind.URGENT,
            f"{task.ref} marked Urgent: {task.title}",
        )


def notify_watchers_status_changed(task, actor):
    for user in task.watchers.exclude(pk=actor.pk):
        notify(
            task,
            user,
            Notification.Kind.STATUS_CHANGED,
            f"{task.ref} status changed to {task.get_status_display()}",
        )


def prune_stale_alerts(task, previous_assignee):
    """
    §7's reassignment exception: delete the previous assignee's pending
    due_soon/overdue rows for this task so the new owner gets their own.
    Unread only — a read alert is already history, not something to hide.
    """
    if previous_assignee is None:
        return
    Notification.objects.filter(
        task=task,
        user=previous_assignee,
        kind__in=[Notification.Kind.DUE_SOON, Notification.Kind.OVERDUE],
        read_at__isnull=True,
    ).delete()
