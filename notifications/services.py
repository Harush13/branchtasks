"""
Notification triggers (spec §7): the three immediate ones fire inline from
tasks/services.py; the two scheduled ones (due_soon/overdue) fire once daily
from `tasks/management/commands/run_task_alerts.py` (Phase 5). Both halves
share `notify()`, so idempotency and the email channel are defined once.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.models import User
from accounts.permissions import is_manager

from .models import Notification


def send_notification_email(notification):
    """
    Best-effort email channel (spec §7), off by default in dev
    (`EMAIL_ENABLED`). `fail_silently` because a dead SMTP server must never
    roll back the in-app notification that was already committed — the bell
    is the channel of record, email is a bonus.
    """
    if not settings.EMAIL_ENABLED or not notification.user.email:
        return
    context = {"notification": notification}
    subject = render_to_string("notifications/email/notification_subject.txt", context).strip()
    body = render_to_string("notifications/email/notification_body.txt", context)
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [notification.user.email],
        fail_silently=True,
    )


def notify(task, user, kind, body):
    """
    Wraps get_or_create on the UNIQUE(task, user, kind) constraint so a
    duplicate trigger (e.g. reassigning back to the same person) is a no-op
    instead of an IntegrityError. First notice for a given (task, user,
    kind) wins; body is not updated on repeat. Email only fires on the row
    that was actually created, not on a no-op repeat.
    """
    notification, created = Notification.objects.get_or_create(
        task=task, user=user, kind=kind, defaults={"body": body}
    )
    if created:
        send_notification_email(notification)


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
