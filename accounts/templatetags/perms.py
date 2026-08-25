"""
Template-level permission guards (spec §5). Every filter here is a thin
wrapper over accounts/permissions.py — the same predicates
accounts/api_permissions.py wraps for DRF — so the template layer and the
API layer can never drift apart.
"""

from django import template

from accounts import permissions as perms

register = template.Library()


@register.filter
def can_edit(user, task):
    return perms.can_edit_task(user, task)


@register.filter
def can_reassign(user):
    return perms.can_reassign(user)


@register.filter
def can_reopen(user):
    return perms.can_reopen(user)


@register.filter
def can_cancel(user):
    return perms.can_cancel(user)


@register.filter
def can_view_dashboard(user):
    return perms.can_view_dashboard(user)


@register.filter
def can_delete_attachment(user, attachment):
    return perms.can_delete_attachment(user, attachment)


@register.filter
def is_manager(user):
    return perms.is_manager(user)
