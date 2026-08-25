"""
§11's status/priority color table, in one place so partials/_status_badge.html
and partials/_priority_badge.html can't drift into two different palettes.
Cancelled and Urgent are deliberately distinct hues (rose-900 vs red-500),
per §11's explicit call-out that two similar reds is not acceptable.
"""

from django import template

from ..models import Task
from ..services import TRANSITIONS

register = template.Library()

_STATUS_ORDER = [
    Task.Status.NEW,
    Task.Status.IN_PROGRESS,
    Task.Status.WAITING,
    Task.Status.DONE,
    Task.Status.CANCELLED,
]

_STATUS_CLASSES = {
    Task.Status.NEW: "bg-gray-100 text-gray-700",
    Task.Status.IN_PROGRESS: "bg-yellow-100 text-yellow-800",
    Task.Status.WAITING: "bg-purple-100 text-purple-800",
    Task.Status.DONE: "bg-green-100 text-green-800",
    Task.Status.CANCELLED: "bg-rose-900 text-white",
}

_PRIORITY_CLASSES = {
    Task.Priority.LOW: "bg-sky-100 text-sky-700",
    Task.Priority.NORMAL: "bg-gray-100 text-gray-600",
    Task.Priority.HIGH: "bg-orange-100 text-orange-800",
    Task.Priority.URGENT: "bg-red-500 text-white",
}


@register.filter
def status_badge_class(status):
    return _STATUS_CLASSES.get(status, "bg-gray-100 text-gray-700")


@register.filter
def priority_badge_class(priority):
    return _PRIORITY_CLASSES.get(priority, "bg-gray-100 text-gray-600")


@register.simple_tag
def legal_transitions(task):
    """Reads the §4 state machine (tasks/services.TRANSITIONS) to list only
    the destination statuses actually legal from here — never a hardcoded
    template list, so the UI can't silently drift from the state machine."""
    allowed = TRANSITIONS.get(task.status, set())
    return [(s, Task.Status(s).label) for s in _STATUS_ORDER if s in allowed]
