"""
DRF permission classes (Phase 3, spec §5). Each one only wraps a predicate
from accounts/permissions.py — no rule logic lives here, so this layer and
Phase 4's template guards can never drift apart from each other.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .permissions import can_delete_attachment, can_edit_task, is_admin, is_manager


class IsManager(BasePermission):
    """Manager or admin — used for reassign/cancel-adjacent endpoints."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_manager(request.user))


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_admin(request.user))


class CanEditTask(BasePermission):
    """§5: visibility is global, so every authenticated user may read (GET/
    HEAD/OPTIONS) any task; only edit rights are restricted to the opener,
    the assignee, or a manager/admin."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return can_edit_task(request.user, obj)


class CanDeleteAttachment(BasePermission):
    def has_object_permission(self, request, view, obj):
        return can_delete_attachment(request.user, obj)
