"""
Phase 4: §11's task list / My Tasks / detail / create screens, rendered
through Django's test Client (session cookies, real template rendering —
not the DRF APIClient the test_api_*.py files use).
"""

import pytest
from django.test import Client
from django.utils import timezone

from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


def logged_in(user):
    client = Client()
    client.force_login(user)
    return client


class TestTaskList:
    def test_list_renders_tasks(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).get("/tasks/")
        assert resp.status_code == 200
        assert task.ref in resp.content.decode()

    def test_list_filters_by_status(self, member, branch, category):
        make_task(branch, category, member, status=Task.Status.NEW)
        done = make_task(
            branch, category, member, status=Task.Status.DONE, completed_at=timezone.now()
        )
        resp = logged_in(member).get("/tasks/", {"status": "new"})
        body = resp.content.decode()
        assert done.ref not in body


class TestMyTasks:
    def test_shows_only_my_active_tasks(self, member, manager, branch, category):
        mine = make_task(branch, category, member, assignee=member)
        others = make_task(branch, category, member, assignee=manager)
        closed = make_task(
            branch,
            category,
            member,
            assignee=member,
            status=Task.Status.DONE,
            completed_at=timezone.now(),
        )
        resp = logged_in(member).get("/tasks/my/")
        body = resp.content.decode()
        assert mine.ref in body
        assert others.ref not in body
        assert closed.ref not in body

    def test_ignores_assignee_override_in_query_string(self, member, manager, branch, category):
        """§11: 'pre-filtered' is enforced server-side, not just hidden UI —
        a hand-crafted ?assignee= can't widen My Tasks to someone else."""
        others = make_task(branch, category, member, assignee=manager)
        resp = logged_in(member).get("/tasks/my/", {"assignee": manager.id})
        assert others.ref not in resp.content.decode()


class TestTaskDetail:
    def test_detail_renders_updates_attachments_history(self, member, branch, category):
        task = make_task(branch, category, member)
        task.updates.create(author=member, body="a comment")
        resp = logged_in(member).get(f"/tasks/{task.ref}/")
        assert resp.status_code == 200
        assert "a comment" in resp.content.decode()

    def test_anonymous_redirected(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = Client().get(f"/tasks/{task.ref}/")
        assert resp.status_code == 302
        assert resp.url.startswith("/login/")


class TestTaskCreate:
    def test_get_renders_form(self, member):
        resp = logged_in(member).get("/tasks/new/")
        assert resp.status_code == 200
        assert 'name="title"' in resp.content.decode()

    def test_post_creates_task_via_service(self, member, branch, category):
        resp = logged_in(member).post(
            "/tasks/new/",
            {"title": "New task", "branch": branch.id, "category": category.id, "priority": 2},
        )
        assert resp.status_code == 302
        task = Task.objects.get(title="New task")
        assert task.opened_by_id == member.id
        assert task.ref.startswith("TSK-")
        assert resp.url == f"/tasks/{task.ref}/"

    def test_post_missing_required_field_reshows_form(self, member):
        resp = logged_in(member).post("/tasks/new/", {"title": "No branch or category"})
        assert resp.status_code == 200
        assert not Task.objects.filter(title="No branch or category").exists()
