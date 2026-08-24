from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from simple_history.models import HistoricalRecords

from core.models import Branch, Category

from .validators import (
    attachment_upload_path,
    validate_attachment_size,
    validate_attachment_type,
)

# Mirrors the DDL's `WHERE status NOT IN ('done', 'cancelled')` filter, used
# by the two partial indexes below and by the deactivation guard in
# accounts/validators.py.
_INACTIVE_STATUSES = ["done", "cancelled"]


class Task(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "חדש"
        IN_PROGRESS = "in_progress", "בטיפול"
        WAITING = "waiting", "ממתין"
        DONE = "done", "הושלם"
        CANCELLED = "cancelled", "בוטל"

    class Priority(models.IntegerChoices):
        LOW = 1, "נמוכה"
        NORMAL = 2, "רגילה"
        HIGH = 3, "גבוהה"
        URGENT = 4, "דחופה"

    # NOT NULL at the DB level (blank=True is form-only). Assigned in save()
    # after the initial insert, since it's derived from the PK — see the
    # docstring on save() for why that isn't a §12 "business logic" violation.
    ref = models.CharField(max_length=16, unique=True, blank=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="tasks")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="tasks")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_tasks"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
    )
    # Status-change notices only (Phase 0 decision) — no due_soon/overdue
    # fan-out, so the Phase 5 daily job's volume doesn't multiply per watcher.
    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="watched_tasks"
    )
    priority = models.SmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    blocker = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(priority__gte=1, priority__lte=4),
                name="task_priority_between_1_4",
            ),
            models.CheckConstraint(
                check=Q(status="done", completed_at__isnull=False)
                | (~Q(status="done") & Q(completed_at__isnull=True)),
                name="completed_only_when_done",
            ),
            models.CheckConstraint(
                check=Q(status="cancelled", cancelled_at__isnull=False)
                | (~Q(status="cancelled") & Q(cancelled_at__isnull=True)),
                name="cancelled_only_when_cancelled",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "due_date"], name="idx_task_status_due"),
            models.Index(
                fields=["assignee"],
                name="idx_task_assignee",
                condition=~Q(status__in=_INACTIVE_STATUSES),
            ),
            models.Index(fields=["branch"], name="idx_task_branch"),
            models.Index(
                fields=["priority"],
                name="idx_task_open_prio",
                condition=~Q(status__in=_INACTIVE_STATUSES),
            ),
            models.Index(fields=["-created_at"], name="idx_task_created"),
        ]

    def __str__(self):
        return f"{self.ref or 'TSK-pending'} {self.title}"

    def save(self, *args, **kwargs):
        """
        `ref` (spec §3.3: 'TSK-' + zero-padded 6-digit id) can only be
        derived after the row has a PK, so creation needs two writes. Both
        are wrapped in one transaction so no other connection can ever read
        a row with a blank ref, and it's plain identity assignment — not a
        status transition or a side effect — so it stays out of services.py.
        """
        is_new = self._state.adding
        if is_new:
            with transaction.atomic():
                super().save(*args, **kwargs)
                self.ref = f"TSK-{self.pk:06d}"
                super().save(update_fields=["ref"])
        else:
            super().save(*args, **kwargs)


class TaskUpdate(models.Model):
    """Threaded comments (spec §3.4)."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="updates")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="task_updates"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["task", "-created_at"], name="idx_update_task")]

    def __str__(self):
        return f"{self.task.ref} · {self.author}"


class Attachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    update = models.ForeignKey(
        TaskUpdate,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_attachments"
    )
    file = models.FileField(
        upload_to=attachment_upload_path,
        max_length=500,
        validators=[validate_attachment_size, validate_attachment_type],
    )
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name
