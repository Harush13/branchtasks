"""
Phase 4: §5's permission table exercised through the template guards
(accounts/templatetags/perms.py) — a member must not even see controls they
can't use, on top of the server-side rejection already covered in
tests/test_views_htmx.py.
"""

import pytest
from django.test import Client

from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


def logged_in(user):
    client = Client()
    client.force_login(user)
    return client


def test_member_does_not_see_reassign_select(member, manager, branch, category):
    task = make_task(branch, category, member)
    resp = logged_in(member).get(f"/tasks/{task.ref}/")
    assert 'name="assignee"' not in resp.content.decode()


def test_manager_sees_reassign_select(manager, member, branch, category):
    task = make_task(branch, category, member)
    resp = logged_in(manager).get(f"/tasks/{task.ref}/")
    assert 'name="assignee"' in resp.content.decode()


def test_member_does_not_see_dashboard_nav_link(member):
    resp = logged_in(member).get("/tasks/")
    body = resp.content.decode()
    assert "לוח בקרה" not in body


def test_manager_sees_dashboard_nav_link(manager):
    resp = logged_in(manager).get("/tasks/")
    body = resp.content.decode()
    assert "לוח בקרה" in body
