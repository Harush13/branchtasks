"""
Phase 6 gate: the HTML dashboard screen (§11) — manager/admin only, counters
partial reachable for the 60s HTMX poll, nav link already covered by
test_views_permissions.py.
"""

import pytest
from django.test import Client

from tasks.models import Task

pytestmark = pytest.mark.django_db


def logged_in(user):
    client = Client()
    client.force_login(user)
    return client


def test_member_gets_403(member):
    resp = logged_in(member).get("/tasks/dashboard/")
    assert resp.status_code == 403


def test_manager_gets_dashboard(manager):
    resp = logged_in(manager).get("/tasks/dashboard/")
    assert resp.status_code == 200
    assert "לוח בקרה" in resp.content.decode()


def test_admin_gets_dashboard(admin_user):
    assert logged_in(admin_user).get("/tasks/dashboard/").status_code == 200


def test_dashboard_passes_status_and_priority_choices_to_chart_labels(manager):
    """
    Regression: DashboardView originally omitted status_choices/
    priority_choices from its context, so the json_script blocks the
    Chart.js legends read from serialized to an empty string and every
    legend rendered as the literal word "undefined" client-side. Caught by
    a live screenshot, not by an earlier status-code-only test.
    """
    resp = logged_in(manager).get("/tasks/dashboard/")
    body = resp.content.decode()
    assert 'id="status-choices"' in body
    assert '["new", "' in body
    assert 'id="priority-choices"' in body
    assert '[1, "' in body


def test_anonymous_redirected_to_login():
    resp = Client().get("/tasks/dashboard/")
    assert resp.status_code == 302
    assert "/login" in resp.url


def test_counters_partial_reflects_state(manager, branch, category, opener):
    Task.objects.create(
        title="t", branch=branch, category=category, opened_by=opener, status=Task.Status.NEW
    )
    resp = logged_in(manager).get("/tasks/dashboard/counters/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'hx-trigger="every 60s"' in body


def test_counters_partial_forbidden_for_member(member):
    resp = logged_in(member).get("/tasks/dashboard/counters/")
    assert resp.status_code == 403
