"""
Phase 4: the inline-edit HTMX endpoints (§11's status/priority/assignee/
due-date editing, plus comments and attachments) — each must return the
re-rendered partial, not a full page, and an illegal transition or a
missing blocker must render an inline error rather than 500.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from tasks.models import Task

pytestmark = pytest.mark.django_db

PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


def logged_in(user):
    client = Client()
    client.force_login(user)
    return client


class TestSetStatus:
    def test_legal_transition_returns_partial(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/status/", {"status": "in_progress"}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert b"<html" not in resp.content
        task.refresh_from_db()
        assert task.status == "in_progress"

    def test_illegal_transition_shows_error_not_500(self, member, branch, category):
        task = make_task(branch, category, member)  # new
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/status/", {"status": "new"}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert "Cannot move task" in resp.content.decode()
        task.refresh_from_db()
        assert task.status == "new"

    def test_waiting_without_blocker_shows_error(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/status/", {"status": "waiting"}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert "blocker is required" in resp.content.decode()
        task.refresh_from_db()
        assert task.status == "new"

    def test_waiting_with_blocker_succeeds(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/status/",
            {"status": "waiting", "blocker": "parts on order"},
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.status == "waiting"
        assert task.blocker == "parts on order"


class TestSetPriority:
    def test_opener_can_change_priority(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/priority/", {"priority": 4}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.priority == 4

    def test_unrelated_member_gets_inline_error(self, member, branch, category):
        from accounts.models import User

        other = User.objects.create_user(username="other_p", password="x")
        task = make_task(branch, category, other)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/priority/", {"priority": 4}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.priority == 2  # unchanged


class TestSetAssignee:
    def test_manager_can_reassign(self, manager, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(manager).post(
            f"/tasks/{task.ref}/assignee/", {"assignee": member.id}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.assignee_id == member.id

    def test_member_direct_post_rejected_not_500(self, member, manager, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/assignee/", {"assignee": manager.id}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.assignee_id is None


class TestAddUpdateAndAttachment:
    def test_add_comment(self, member, branch, category):
        task = make_task(branch, category, member)
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/updates/", {"body": "status check"}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert task.updates.filter(body="status check").exists()

    def test_upload_valid_attachment(self, member, branch, category):
        task = make_task(branch, category, member)
        upload = SimpleUploadedFile("photo.png", PNG_MAGIC, content_type="image/png")
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/attachments/", {"file": upload}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert task.attachments.filter(original_name="photo.png").exists()

    def test_upload_disallowed_type_shows_error_not_500(self, member, branch, category):
        task = make_task(branch, category, member)
        upload = SimpleUploadedFile("notes.txt", b"plain text", content_type="text/plain")
        resp = logged_in(member).post(
            f"/tasks/{task.ref}/attachments/", {"file": upload}, HTTP_HX_REQUEST="true"
        )
        assert resp.status_code == 200
        assert task.attachments.count() == 0
