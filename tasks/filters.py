"""
Parses §6's GET /api/tasks query parameters and hands them to
tasks/selectors.filter_tasks — a django_filters.FilterSet would just
re-express rules that selector already implements and tests, so this stays a
plain function instead (one source of truth, same reasoning §5 applies to
permissions).
"""

import datetime

from rest_framework.exceptions import ValidationError

from .selectors import filter_tasks, order_tasks

ORDERING_WHITELIST = {"priority", "due_date", "created_at", "updated_at", "status", "ref"}


def _parse_date(value, param_name):
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({param_name: f"'{value}' is not a valid ISO date."}) from exc


def _parse_int(value, param_name):
    try:
        return int(value)
    except ValueError as exc:
        raise ValidationError({param_name: f"'{value}' is not a valid integer."}) from exc


def apply_query_params(qs, query_params):
    """query_params is request.query_params (a QueryDict) — repeatable keys
    (status) are read with getlist, everything else with a plain lookup."""
    status = query_params.getlist("status") or None
    overdue = query_params.get("overdue") == "1"

    qs = filter_tasks(
        qs,
        branch=query_params.get("branch") or None,
        category=query_params.get("category") or None,
        status=status,
        assignee=query_params.get("assignee") or None,
        opened_by=query_params.get("opened_by") or None,
        priority_min=(
            _parse_int(query_params["priority_min"], "priority_min")
            if query_params.get("priority_min")
            else None
        ),
        overdue=overdue,
        due_before=(
            _parse_date(query_params["due_before"], "due_before")
            if query_params.get("due_before")
            else None
        ),
        due_after=(
            _parse_date(query_params["due_after"], "due_after")
            if query_params.get("due_after")
            else None
        ),
        q=query_params.get("q") or None,
    )

    return order_tasks(qs, _parse_ordering(query_params.get("ordering")))


def _parse_ordering(raw):
    if not raw:
        return None
    fields = [f.strip() for f in raw.split(",") if f.strip()]
    for field in fields:
        bare = field[1:] if field.startswith("-") else field
        if bare not in ORDERING_WHITELIST:
            allowed = sorted(ORDERING_WHITELIST)
            raise ValidationError(
                {"ordering": f"'{field}' is not an orderable field. Allowed: {allowed}."}
            )
    return fields
