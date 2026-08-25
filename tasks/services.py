"""
Every write to a Task goes through here (spec §12). Views/serializers and the
Admin stay thin — none of them may set `task.status` directly (§4).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.permissions import can_cancel, can_edit_task, can_reassign, can_reopen
from notifications.services import (
    notify_assigned,
    notify_reassigned,
    notify_urgent,
    notify_watchers_status_changed,
    prune_stale_alerts,
)

from .models import Attachment, Task, TaskUpdate

# Spec §4's transition table. 'done' and 'cancelled' only reopen to
# in_progress, and only for an admin actor (enforced below, not here).
TRANSITIONS = {
    Task.Status.NEW: {
        Task.Status.IN_PROGRESS,
        Task.Status.WAITING,
        Task.Status.DONE,
        Task.Status.CANCELLED,
    },
    Task.Status.IN_PROGRESS: {
        Task.Status.NEW,
        Task.Status.WAITING,
        Task.Status.DONE,
        Task.Status.CANCELLED,
    },
    Task.Status.WAITING: {Task.Status.IN_PROGRESS, Task.Status.DONE, Task.Status.CANCELLED},
    Task.Status.DONE: {Task.Status.IN_PROGRESS},
    Task.Status.CANCELLED: {Task.Status.IN_PROGRESS},
}

_REOPEN_FROM = {Task.Status.DONE, Task.Status.CANCELLED}


@transaction.atomic
def change_status(task, new_status, actor, blocker=None):
    """Single entry point for every status change. Raises on invalid input."""
    old_status = task.status

    if new_status not in TRANSITIONS.get(old_status, set()):
        raise ValidationError(f"Cannot move task from '{old_status}' to '{new_status}'.")

    if old_status in _REOPEN_FROM and not can_reopen(actor):
        raise PermissionDenied("Only an admin may reopen a closed task.")

    if new_status == Task.Status.CANCELLED and not can_cancel(actor):
        raise PermissionDenied("Only a manager or admin may cancel a task.")

    if new_status == Task.Status.WAITING and not (blocker or "").strip():
        raise ValidationError("A blocker is required to move a task to 'waiting'.")

    now = timezone.now()
    task.status = new_status
    if new_status == Task.Status.WAITING:
        task.blocker = blocker.strip()
    if new_status == Task.Status.DONE:
        task.completed_at = now
    elif old_status == Task.Status.DONE:
        task.completed_at = None
    if new_status == Task.Status.CANCELLED:
        task.cancelled_at = now
    elif old_status == Task.Status.CANCELLED:
        task.cancelled_at = None

    task.save()
    notify_watchers_status_changed(task, actor)
    return task


@transaction.atomic
def create_task(actor, *, title, branch, category, **fields):
    """Any authenticated member may create a task (§5).

    `watchers` is a ManyToManyField — it can't be passed to Task.objects.create()
    like a normal kwarg (Django raises on direct M2M assignment at construction
    time), so it's split out and applied via .set() once the row has a PK.
    """
    assignee = fields.get("assignee")
    priority = fields.get("priority", Task.Priority.NORMAL)
    watchers = fields.pop("watchers", None)

    task = Task.objects.create(
        title=title,
        branch=branch,
        category=category,
        opened_by=actor,
        priority=priority,
        **{k: v for k, v in fields.items() if k not in ("priority",)},
    )
    if watchers:
        task.watchers.set(watchers)

    if assignee:
        notify_assigned(task, actor)
    if priority == Task.Priority.URGENT:
        notify_urgent(task, actor)
    return task


@transaction.atomic
def assign_task(task, new_assignee, actor):
    if not can_reassign(actor):
        raise PermissionDenied("Only a manager or admin may reassign a task.")

    previous_assignee = task.assignee
    task.assignee = new_assignee
    task.save(update_fields=["assignee", "updated_at"])

    prune_stale_alerts(task, previous_assignee)
    if new_assignee:
        notify_reassigned(task, actor)
    return task


@transaction.atomic
def update_task_fields(task, actor, **fields):
    """
    Mutable-field edit, mirroring §6's PATCH endpoint. Status changes carry
    side effects that belong in change_status, not here — reject them so
    every caller is pointed at the dedicated entry point.
    """
    if "status" in fields:
        raise ValidationError(
            "Use change_status() to change status — it is not a plain field edit."
        )
    if not can_edit_task(actor, task):
        raise PermissionDenied("You may only edit tasks you opened or are assigned to.")

    # `watchers` is a ManyToManyField — setattr() raises on it the same way
    # Task.objects.create() does (see create_task's docstring); .set() is the
    # only valid write path once the row already has a PK.
    watchers = fields.pop("watchers", None)
    for key, value in fields.items():
        setattr(task, key, value)
    if watchers is not None:
        task.watchers.set(watchers)
    task.save()
    return task


@transaction.atomic
def add_update(task, author, body):
    return TaskUpdate.objects.create(task=task, author=author, body=body)


@transaction.atomic
def attach_file(task, uploaded_by, file, update=None):
    """
    `file` is a Django UploadedFile. FileField validators are not invoked by
    plain save() — only full_clean() runs them — so this calls full_clean()
    explicitly to enforce the size/MIME rules in tasks/validators.py.
    """
    attachment = Attachment(
        task=task,
        update=update,
        uploaded_by=uploaded_by,
        file=file,
        original_name=getattr(file, "name", ""),
        mime_type=getattr(file, "content_type", "") or "",
        size_bytes=getattr(file, "size", None),
    )
    attachment.full_clean()
    attachment.save()
    return attachment
