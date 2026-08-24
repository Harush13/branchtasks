"""
Phase 1 tests: what the schema itself enforces. State-machine behavior
(change_status, notifications, etc.) is Phase 2 — these only cover
constraints, the ref generator, and the deactivation guard.
"""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from accounts.models import User
from accounts.validators import assert_can_deactivate
from core.models import Branch, Category
from tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def branch():
    return Branch.objects.create(name_he="תל יצחק", name_en="Tel Yitzhak")


@pytest.fixture
def category():
    return Category.objects.create(name_he="תפעול", name_en="Operations")


@pytest.fixture
def opener():
    return User.objects.create_user(username="opener", password="x")


def make_task(branch, category, opener, **kwargs):
    return Task.objects.create(
        title="Fix the thing",
        branch=branch,
        category=category,
        opened_by=opener,
        **kwargs,
    )


class TestRefGenerator:
    def test_ref_format(self, branch, category, opener):
        task = make_task(branch, category, opener)
        assert task.ref == f"TSK-{task.pk:06d}"

    def test_ref_unique_across_a_batch(self, branch, category, opener):
        tasks = [make_task(branch, category, opener) for _ in range(5)]
        refs = [t.ref for t in tasks]
        assert len(refs) == len(set(refs))

    def test_ref_not_blank_after_save(self, branch, category, opener):
        task = make_task(branch, category, opener)
        assert task.ref != ""
        task.refresh_from_db()
        assert task.ref != ""


class TestPriorityConstraint:
    def test_priority_out_of_range_rejected(self, branch, category, opener):
        with pytest.raises(IntegrityError):
            make_task(branch, category, opener, priority=5)


class TestCompletedAtConstraint:
    def test_done_without_completed_at_rejected(self, branch, category, opener):
        with pytest.raises(IntegrityError):
            make_task(branch, category, opener, status=Task.Status.DONE)

    def test_completed_at_without_done_rejected(self, branch, category, opener):
        with pytest.raises(IntegrityError):
            make_task(branch, category, opener, status=Task.Status.NEW, completed_at=timezone.now())

    def test_done_with_completed_at_allowed(self, branch, category, opener):
        task = make_task(
            branch, category, opener, status=Task.Status.DONE, completed_at=timezone.now()
        )
        assert task.status == Task.Status.DONE


class TestCancelledAtConstraint:
    def test_cancelled_without_cancelled_at_rejected(self, branch, category, opener):
        with pytest.raises(IntegrityError):
            make_task(branch, category, opener, status=Task.Status.CANCELLED)

    def test_cancelled_with_cancelled_at_allowed(self, branch, category, opener):
        task = make_task(
            branch, category, opener, status=Task.Status.CANCELLED, cancelled_at=timezone.now()
        )
        assert task.status == Task.Status.CANCELLED


class TestDeactivationGuard:
    def test_blocked_while_assignee_on_active_task(self, branch, category, opener):
        assignee = User.objects.create_user(username="assignee", password="x")
        make_task(branch, category, opener, assignee=assignee, status=Task.Status.IN_PROGRESS)
        with pytest.raises(ValidationError):
            assert_can_deactivate(assignee)

    def test_allowed_when_no_active_tasks(self, branch, category, opener):
        assignee = User.objects.create_user(username="assignee2", password="x")
        assert_can_deactivate(assignee)  # does not raise

    def test_allowed_when_only_done_tasks(self, branch, category, opener):
        assignee = User.objects.create_user(username="assignee3", password="x")
        make_task(
            branch,
            category,
            opener,
            assignee=assignee,
            status=Task.Status.DONE,
            completed_at=timezone.now(),
        )
        assert_can_deactivate(assignee)  # does not raise


class TestLookupOrdering:
    def test_branch_str_is_hebrew_name(self, branch):
        assert str(branch) == "תל יצחק"

    def test_due_date_optional(self, branch, category, opener):
        task = make_task(branch, category, opener)
        assert task.due_date is None
        task2 = make_task(branch, category, opener, due_date=date(2026, 9, 1))
        assert task2.due_date == date(2026, 9, 1)
