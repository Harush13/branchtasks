from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    Model only in Phase 1 — the triggers and the daily `run_task_alerts`
    job that populate this table are Phase 5 (spec §7). The
    UNIQUE(task, user, kind) constraint is what makes that job idempotent
    via get_or_create; it's defined now so the schema is right from the
    start.
    """

    class Kind(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        REASSIGNED = "reassigned", "Reassigned"
        URGENT = "urgent", "Urgent"
        DUE_SOON = "due_soon", "Due soon"
        OVERDUE = "overdue", "Overdue"
        STATUS_CHANGED = "status_changed", "Status changed"  # watcher notices

    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    body = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "user", "kind"], name="uniq_task_user_kind")
        ]
        indexes = [
            models.Index(
                fields=["user"], name="idx_notif_unread", condition=models.Q(read_at__isnull=True)
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} → {self.user} ({self.task.ref})"
