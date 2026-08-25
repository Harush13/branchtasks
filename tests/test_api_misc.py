"""
Phase 3: the remaining §6 endpoints not covered by test_api_status.py /
test_api_permissions.py — meta, comments, attachment upload, notifications.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from notifications.models import Notification
from tasks.models import Task

pytestmark = pytest.mark.django_db

PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


class TestMeta:
    def test_meta_lists_active_branches_categories_users(
        self, member_client, branch, category, member
    ):
        resp = member_client.get("/api/meta")
        assert resp.status_code == 200
        body = resp.json()
        assert {b["id"] for b in body["branches"]} >= {branch.id}
        assert {c["id"] for c in body["categories"]} >= {category.id}
        assert {u["id"] for u in body["users"]} >= {member.id}

    def test_meta_excludes_inactive_branch(self, member_client, branch):
        branch.is_active = False
        branch.save()
        resp = member_client.get("/api/meta")
        assert branch.id not in {b["id"] for b in resp.json()["branches"]}


class TestTaskCreate:
    def test_member_can_create_task(self, member_client, branch, category):
        resp = member_client.post(
            "/api/tasks",
            {"title": "New task", "branch": branch.id, "category": category.id},
        )
        assert resp.status_code == 201
        assert resp.json()["ref"].startswith("TSK-")

    def test_create_rejects_missing_required_fields(self, member_client):
        resp = member_client.post("/api/tasks", {"title": "No branch or category"})
        assert resp.status_code == 400


class TestTaskDetail:
    """Regression test for a real bug: prefetch_related("history") raised
    ValueError because django-simple-history's `history` isn't a genuine
    reverse FK — nothing in Phase 3 originally exercised GET /api/tasks/{ref}
    to catch it."""

    def test_retrieve_renders_updates_attachments_history(
        self, member_client, member, branch, category
    ):
        task = make_task(branch, category, member)
        task.updates.create(author=member, body="a comment")
        resp = member_client.get(f"/api/tasks/{task.ref}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ref"] == task.ref
        assert len(body["updates"]) == 1
        assert body["history"]


class TestComments:
    def test_add_comment(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        resp = member_client.post(f"/api/tasks/{task.ref}/updates", {"body": "status check"})
        assert resp.status_code == 201
        assert resp.json()["body"] == "status check"
        assert task.updates.count() == 1


class TestAttachments:
    def test_upload_valid_attachment(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        upload = SimpleUploadedFile("photo.png", PNG_MAGIC, content_type="image/png")
        resp = member_client.post(
            f"/api/tasks/{task.ref}/attachments", {"file": upload}, format="multipart"
        )
        assert resp.status_code == 201
        assert resp.json()["original_name"] == "photo.png"

    def test_upload_rejects_disallowed_type(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        upload = SimpleUploadedFile(
            "notes.txt", b"plain text, no magic bytes", content_type="text/plain"
        )
        resp = member_client.post(
            f"/api/tasks/{task.ref}/attachments", {"file": upload}, format="multipart"
        )
        assert resp.status_code == 400


class TestNotifications:
    def test_list_only_returns_own_unread(self, member_client, member, manager, branch, category):
        task = make_task(branch, category, member)
        Notification.objects.create(
            task=task, user=member, kind=Notification.Kind.ASSIGNED, body="mine"
        )
        Notification.objects.create(
            task=task, user=manager, kind=Notification.Kind.ASSIGNED, body="not mine"
        )
        resp = member_client.get("/api/notifications")
        bodies = [row["body"] for row in resp.json()["results"]]
        assert bodies == ["mine"]

    def test_mark_read(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        notif = Notification.objects.create(
            task=task, user=member, kind=Notification.Kind.ASSIGNED, body="mine"
        )
        resp = member_client.post(f"/api/notifications/{notif.id}/read")
        assert resp.status_code == 200
        notif.refresh_from_db()
        assert notif.read_at is not None

    def test_cannot_mark_other_users_notification_read(
        self, member_client, manager, branch, category
    ):
        task = make_task(branch, category, manager)
        notif = Notification.objects.create(
            task=task, user=manager, kind=Notification.Kind.ASSIGNED, body="not mine"
        )
        resp = member_client.post(f"/api/notifications/{notif.id}/read")
        assert resp.status_code == 404
        notif.refresh_from_db()
        assert notif.read_at is None

    def test_mark_all_read(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        Notification.objects.create(
            task=task, user=member, kind=Notification.Kind.ASSIGNED, body="a"
        )
        Notification.objects.create(task=task, user=member, kind=Notification.Kind.URGENT, body="b")
        resp = member_client.post("/api/notifications/read-all")
        assert resp.status_code == 204
        assert not Notification.objects.filter(user=member, read_at__isnull=True).exists()
