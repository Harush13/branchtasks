import pytest

from accounts.models import User
from accounts.permissions import (
    can_cancel,
    can_delete_attachment,
    can_edit_task,
    can_reassign,
    can_reopen,
    can_view_dashboard,
    is_admin,
    is_manager,
)
from tasks.models import Task

pytestmark = pytest.mark.django_db


class TestRoleChecks:
    def test_is_manager(self, member, manager, admin_user):
        assert is_manager(member) is False
        assert is_manager(manager) is True
        assert is_manager(admin_user) is True

    def test_is_admin(self, member, manager, admin_user):
        assert is_admin(member) is False
        assert is_admin(manager) is False
        assert is_admin(admin_user) is True


class TestCanEditTask:
    def test_opener_can_edit(self, branch, category, member, manager):
        task = Task.objects.create(title="T", branch=branch, category=category, opened_by=member)
        assert can_edit_task(member, task) is True
        assert can_edit_task(manager, task) is True  # manager can edit any task

    def test_assignee_can_edit(self, branch, category, member, manager):
        other = User.objects.create_user(username="opener2", password="x")
        task = Task.objects.create(
            title="T", branch=branch, category=category, opened_by=other, assignee=member
        )
        assert can_edit_task(member, task) is True

    def test_unrelated_member_cannot_edit(self, branch, category, member):
        other_opener = User.objects.create_user(username="opener3", password="x")
        unrelated = User.objects.create_user(username="bystander", password="x")
        task = Task.objects.create(
            title="T", branch=branch, category=category, opened_by=other_opener
        )
        assert can_edit_task(unrelated, task) is False


class TestReassignReopenCancel:
    def test_can_reassign(self, member, manager, admin_user):
        assert can_reassign(member) is False
        assert can_reassign(manager) is True
        assert can_reassign(admin_user) is True

    def test_can_reopen_admin_only(self, member, manager, admin_user):
        assert can_reopen(member) is False
        assert can_reopen(manager) is False
        assert can_reopen(admin_user) is True

    def test_can_cancel(self, member, manager, admin_user):
        assert can_cancel(member) is False
        assert can_cancel(manager) is True
        assert can_cancel(admin_user) is True

    def test_can_view_dashboard(self, member, manager, admin_user):
        assert can_view_dashboard(member) is False
        assert can_view_dashboard(manager) is True
        assert can_view_dashboard(admin_user) is True


class TestCanDeleteAttachment:
    def test_uploader_can_delete_own(self, branch, category, member):
        from tasks.models import Attachment

        task = Task.objects.create(title="T", branch=branch, category=category, opened_by=member)
        attachment = Attachment(task=task, uploaded_by=member, original_name="x.png")
        assert can_delete_attachment(member, attachment) is True

    def test_unrelated_member_and_manager_cannot_delete(
        self, branch, category, member, manager, admin_user
    ):
        """§6: uploader-or-admin only — a manager with no stake in the file
        cannot delete it, unlike the broader manager-can-edit-anything rule."""
        from tasks.models import Attachment

        task = Task.objects.create(title="T", branch=branch, category=category, opened_by=member)
        attachment = Attachment(task=task, uploaded_by=member, original_name="x.png")
        other = User.objects.create_user(username="other2", password="x")
        assert can_delete_attachment(other, attachment) is False
        assert can_delete_attachment(manager, attachment) is False
        assert can_delete_attachment(admin_user, attachment) is True
