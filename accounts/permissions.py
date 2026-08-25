"""
Shared permission predicates (spec §5). Plain functions, no request object —
Phase 3's DRF permission classes and Phase 4's template tags both wrap these
so the two layers cannot drift apart.
"""

from accounts.models import User


def is_manager(user):
    """Manager or admin — the two roles with elevated capabilities in §5."""
    return user.role in (User.Role.MANAGER, User.Role.ADMIN)


def is_admin(user):
    return user.role == User.Role.ADMIN


def can_edit_task(user, task):
    """Edit non-status fields: manager/admin, or the opener, or the assignee."""
    return is_manager(user) or task.opened_by_id == user.id or task.assignee_id == user.id


def can_reassign(user):
    """§5: 'Reassign any task' is its own row, separate from 'edit a task
    they opened or are assigned' — members cannot reassign even their own task."""
    return is_manager(user)


def can_reopen(user):
    """§4: reopening a closed task (done/cancelled -> in_progress) is admin-only."""
    return is_admin(user)


def can_cancel(user):
    """Phase 0 decision: cancel narrows §4's transition table to manager/admin."""
    return is_manager(user)


def can_view_dashboard(user):
    return is_manager(user)


def can_delete_attachment(user, attachment):
    """§6: DELETE /api/attachments/{id} is uploader-or-admin — narrower than the
    general manager-can-edit-anything rule, since a manager who never touched
    the file has no more claim to delete it than any other non-uploader."""
    return is_admin(user) or attachment.uploaded_by_id == user.id
