"""
Phase 3: §5's permission table exercised over HTTP, on top of the
already-tested predicates in accounts/permissions.py — this file is about
the view/permission-class wiring, not the rules themselves.
"""

import pytest
from django.utils import timezone

from accounts.models import User
from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


class TestEditBoundary:
    def test_opener_can_patch_own_task(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        resp = member_client.patch(f"/api/tasks/{task.ref}", {"title": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Renamed"

    def test_unrelated_member_cannot_patch(self, member_client, branch, category):
        other = User.objects.create_user(username="other_opener", password="x")
        task = make_task(branch, category, other)
        resp = member_client.patch(f"/api/tasks/{task.ref}", {"title": "Hijacked"})
        assert resp.status_code == 403

    def test_manager_can_patch_any_task(self, manager_client, member, branch, category):
        task = make_task(branch, category, member)
        resp = manager_client.patch(f"/api/tasks/{task.ref}", {"title": "Manager edit"})
        assert resp.status_code == 200


class TestReassignBoundary:
    def test_member_cannot_reassign(self, member_client, member, manager, branch, category):
        task = make_task(branch, category, member)
        resp = member_client.patch(f"/api/tasks/{task.ref}", {"assignee": manager.id})
        assert resp.status_code == 403

    def test_manager_can_reassign(self, manager_client, member, manager, branch, category):
        task = make_task(branch, category, member)
        resp = manager_client.patch(f"/api/tasks/{task.ref}", {"assignee": member.id})
        assert resp.status_code == 200
        assert resp.json()["assignee"]["id"] == member.id


class TestStatusBoundary:
    def test_manager_cannot_reopen_done(self, manager_client, member, branch, category):
        task = make_task(branch, category, member)
        task.status, task.completed_at = Task.Status.DONE, timezone.now()
        task.save()
        resp = manager_client.post(f"/api/tasks/{task.ref}/status", {"status": "in_progress"})
        assert resp.status_code == 403

    def test_admin_can_reopen_done(self, admin_client, member, branch, category):
        task = make_task(branch, category, member)
        task.status, task.completed_at = Task.Status.DONE, timezone.now()
        task.save()
        resp = admin_client.post(f"/api/tasks/{task.ref}/status", {"status": "in_progress"})
        assert resp.status_code == 200

    def test_member_cannot_cancel(self, member_client, member, branch, category):
        task = make_task(branch, category, member)
        resp = member_client.post(f"/api/tasks/{task.ref}/status", {"status": "cancelled"})
        assert resp.status_code == 403

    def test_manager_can_cancel(self, manager_client, member, branch, category):
        task = make_task(branch, category, member)
        resp = manager_client.post(f"/api/tasks/{task.ref}/status", {"status": "cancelled"})
        assert resp.status_code == 200


class TestAttachmentDeleteBoundary:
    def test_uploader_can_delete_own(self, member_client, member, branch, category):
        from tasks.models import Attachment

        task = make_task(branch, category, member)
        attachment = Attachment.objects.create(task=task, uploaded_by=member, original_name="x.png")
        resp = member_client.delete(f"/api/attachments/{attachment.id}")
        assert resp.status_code == 204

    def test_manager_cannot_delete_others_attachment(
        self, manager_client, member, branch, category
    ):
        from tasks.models import Attachment

        task = make_task(branch, category, member)
        attachment = Attachment.objects.create(task=task, uploaded_by=member, original_name="x.png")
        resp = manager_client.delete(f"/api/attachments/{attachment.id}")
        assert resp.status_code == 403

    def test_admin_can_delete_any_attachment(self, admin_client, member, branch, category):
        from tasks.models import Attachment

        task = make_task(branch, category, member)
        attachment = Attachment.objects.create(task=task, uploaded_by=member, original_name="x.png")
        resp = admin_client.delete(f"/api/attachments/{attachment.id}")
        assert resp.status_code == 204
