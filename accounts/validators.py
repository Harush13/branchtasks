from django.core.exceptions import ValidationError

# Statuses that count as "active" for the deactivation guard — mirrors the
# NOT IN ('done', 'cancelled') filter used throughout the spec (overdue,
# dashboard counters, assignee-load index).
ACTIVE_STATUSES = ["new", "in_progress", "waiting"]


def assert_can_deactivate(user):
    """
    Raises ValidationError if `user` is the assignee on any active task.
    Deactivating such a user would silently orphan those tasks (Phase 0
    decision: block until reassigned, rather than auto-unassign).
    """
    from tasks.models import Task

    active = Task.objects.filter(assignee=user, status__in=ACTIVE_STATUSES)
    if active.exists():
        refs = ", ".join(active.values_list("ref", flat=True))
        raise ValidationError(
            f"Cannot deactivate {user}: still assigned to active task(s) {refs}. "
            "Reassign them first."
        )
