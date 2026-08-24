"""
Phase 2 gate: the full §4 transition matrix, blocker enforcement, reopen/
cancel role gates, and the notification triggers that ride along with them.
"""

import itertools

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import User
from core.models import Branch, Category
from notifications.models import Notification
from tasks.models import Task
from tasks.services import (
    TRANSITIONS,
    add_update,
    assign_task,
    attach_file,
    change_status,
    create_task,
    update_task_fields,
)

pytestmark = pytest.mark.django_db

ALL_STATUSES = list(Task.Status.values)

# The exact §4 table, transcribed independently of TRANSITIONS so a bug in
# the implementation can't hide behind a matching bug in the test.
EXPECTED_LEGAL = {
    ("new", "in_progress"),
    ("new", "waiting"),
    ("new", "done"),
    ("new", "cancelled"),
    ("in_progress", "new"),
    ("in_progress", "waiting"),
    ("in_progress", "done"),
    ("in_progress", "cancelled"),
    ("waiting", "in_progress"),
    ("waiting", "done"),
    ("waiting", "cancelled"),
    ("done", "in_progress"),
    ("cancelled", "in_progress"),
}


@pytest.fixture
def branch():
    return Branch.objects.create(name_he="תל יצחק", name_en="Tel Yitzhak")


@pytest.fixture
def category():
    return Category.objects.create(name_he="תפעול", name_en="Operations")


@pytest.fixture
def member(branch):
    return User.objects.create_user(username="member1", password="x", role=User.Role.MEMBER)


@pytest.fixture
def manager():
    return User.objects.create_user(username="manager1", password="x", role=User.Role.MANAGER)


@pytest.fixture
def admin_user():
    return User.objects.create_user(username="admin1", password="x", role=User.Role.ADMIN)


def make_task(branch, category, opener, **kwargs):
    return Task.objects.create(
        title="Fix the thing", branch=branch, category=category, opened_by=opener, **kwargs
    )


def force_status(task, status, **extra):
    """Bypass change_status to seed a task directly in the 'from' state under
    test — this file is testing change_status, so seeding must not use it."""
    Task.objects.filter(pk=task.pk).update(status=status, **extra)
    task.refresh_from_db()
    return task


class TestTransitionMatrix:
    @pytest.mark.parametrize("from_status,to_status", list(itertools.permutations(ALL_STATUSES, 2)))
    def test_matrix_matches_spec_table(
        self, branch, category, member, admin_user, from_status, to_status
    ):
        task = make_task(branch, category, member)
        extra = {}
        if from_status == Task.Status.WAITING:
            extra["blocker"] = "blocked on vendor"
        if from_status == Task.Status.DONE:
            extra["completed_at"] = timezone.now()
        if from_status == Task.Status.CANCELLED:
            extra["cancelled_at"] = timezone.now()
        force_status(task, from_status, **extra)

        legal = (from_status, to_status) in EXPECTED_LEGAL
        assert legal == (to_status in TRANSITIONS[from_status])

        kwargs = {"blocker": "blocked on vendor"} if to_status == Task.Status.WAITING else {}

        if not legal:
            with pytest.raises(ValidationError):
                change_status(task, to_status, admin_user, **kwargs)
            return

        change_status(task, to_status, admin_user, **kwargs)
        task.refresh_from_db()
        assert task.status == to_status


class TestReopenRequiresAdmin:
    def test_manager_cannot_reopen_done(self, branch, category, member, manager):
        task = make_task(branch, category, member)
        force_status(task, Task.Status.DONE, completed_at=timezone.now())
        with pytest.raises(PermissionDenied):
            change_status(task, Task.Status.IN_PROGRESS, manager)

    def test_admin_can_reopen_done(self, branch, category, member, admin_user):
        task = make_task(branch, category, member)
        force_status(task, Task.Status.DONE, completed_at=timezone.now())
        change_status(task, Task.Status.IN_PROGRESS, admin_user)
        task.refresh_from_db()
        assert task.status == Task.Status.IN_PROGRESS
        assert task.completed_at is None

    def test_admin_reopen_cancelled_clears_cancelled_at(self, branch, category, member, admin_user):
        task = make_task(branch, category, member)
        force_status(task, Task.Status.CANCELLED, cancelled_at=timezone.now())
        change_status(task, Task.Status.IN_PROGRESS, admin_user)
        task.refresh_from_db()
        assert task.cancelled_at is None


class TestCancelRequiresManager:
    def test_member_cannot_cancel(self, branch, category, member):
        task = make_task(branch, category, member)
        with pytest.raises(PermissionDenied):
            change_status(task, Task.Status.CANCELLED, member)

    def test_manager_can_cancel(self, branch, category, member, manager):
        task = make_task(branch, category, member)
        change_status(task, Task.Status.CANCELLED, manager)
        task.refresh_from_db()
        assert task.status == Task.Status.CANCELLED
        assert task.cancelled_at is not None


class TestBlockerEnforcement:
    def test_waiting_without_blocker_rejected(self, branch, category, member):
        task = make_task(branch, category, member)
        with pytest.raises(ValidationError):
            change_status(task, Task.Status.WAITING, member)

    def test_waiting_with_blank_blocker_rejected(self, branch, category, member):
        task = make_task(branch, category, member)
        with pytest.raises(ValidationError):
            change_status(task, Task.Status.WAITING, member, blocker="   ")

    def test_waiting_with_blocker_allowed(self, branch, category, member):
        task = make_task(branch, category, member)
        change_status(task, Task.Status.WAITING, member, blocker="waiting on parts")
        task.refresh_from_db()
        assert task.status == Task.Status.WAITING
        assert task.blocker == "waiting on parts"


class TestTimestampStamping:
    def test_done_stamps_completed_at(self, branch, category, member):
        task = make_task(branch, category, member)
        change_status(task, Task.Status.DONE, member)
        task.refresh_from_db()
        assert task.completed_at is not None

    def test_cancelled_stamps_cancelled_at(self, branch, category, member, manager):
        task = make_task(branch, category, member)
        change_status(task, Task.Status.CANCELLED, manager)
        task.refresh_from_db()
        assert task.cancelled_at is not None


class TestNotificationTriggers:
    def test_create_with_assignee_notifies_assignee(self, branch, category, member, manager):
        task = create_task(
            member, title="Do it", branch=branch, category=category, assignee=manager
        )
        assert Notification.objects.filter(
            task=task, user=manager, kind=Notification.Kind.ASSIGNED
        ).exists()

    def test_create_urgent_notifies_managers(self, branch, category, member, manager, admin_user):
        task = create_task(
            member,
            title="Fire!",
            branch=branch,
            category=category,
            priority=Task.Priority.URGENT,
        )
        assert Notification.objects.filter(
            task=task, user=manager, kind=Notification.Kind.URGENT
        ).exists()
        assert Notification.objects.filter(
            task=task, user=admin_user, kind=Notification.Kind.URGENT
        ).exists()

    def test_reassign_notifies_new_assignee_and_prunes_old_alerts(
        self, branch, category, member, manager, admin_user
    ):
        old_assignee = User.objects.create_user(username="old_a", password="x")
        task = make_task(branch, category, member, assignee=old_assignee)
        Notification.objects.create(
            task=task, user=old_assignee, kind=Notification.Kind.OVERDUE, body="stale"
        )

        assign_task(task, manager, admin_user)

        assert Notification.objects.filter(
            task=task, user=manager, kind=Notification.Kind.REASSIGNED
        ).exists()
        assert not Notification.objects.filter(
            task=task, user=old_assignee, kind=Notification.Kind.OVERDUE
        ).exists()

    def test_double_trigger_produces_one_notification(
        self, branch, category, member, manager, admin_user
    ):
        task = make_task(branch, category, member, assignee=manager)
        assign_task(task, manager, admin_user)
        assign_task(task, manager, admin_user)
        assert (
            Notification.objects.filter(
                task=task, user=manager, kind=Notification.Kind.REASSIGNED
            ).count()
            == 1
        )

    def test_member_cannot_reassign(self, branch, category, member, manager):
        task = make_task(branch, category, member)
        with pytest.raises(PermissionDenied):
            assign_task(task, manager, member)


class TestUpdateTaskFields:
    def test_status_key_rejected(self, branch, category, member):
        task = make_task(branch, category, member)
        with pytest.raises(ValidationError):
            update_task_fields(task, member, status=Task.Status.DONE)

    def test_opener_can_edit_own_task(self, branch, category, member):
        task = make_task(branch, category, member)
        update_task_fields(task, member, title="Renamed")
        task.refresh_from_db()
        assert task.title == "Renamed"

    def test_unrelated_member_cannot_edit(self, branch, category, member):
        task = make_task(branch, category, member)
        other = User.objects.create_user(username="other", password="x")
        with pytest.raises(PermissionDenied):
            update_task_fields(task, other, title="Hijacked")


PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


class TestAddUpdateAndAttachFile:
    def test_add_update_creates_row(self, branch, category, member):
        task = make_task(branch, category, member)
        update = add_update(task, member, "status check")
        assert update.task_id == task.id
        assert update.author_id == member.id

    def test_attach_valid_file_stores_metadata(self, branch, category, member):
        task = make_task(branch, category, member)
        upload = SimpleUploadedFile("photo.png", PNG_MAGIC, content_type="image/png")
        attachment = attach_file(task, member, upload)
        assert attachment.task_id == task.id
        assert attachment.original_name == "photo.png"
        assert attachment.size_bytes == len(PNG_MAGIC)

    def test_attach_disallowed_type_rejected(self, branch, category, member):
        task = make_task(branch, category, member)
        upload = SimpleUploadedFile(
            "notes.txt", b"plain text, no magic bytes", content_type="text/plain"
        )
        with pytest.raises(ValidationError):
            attach_file(task, member, upload)
