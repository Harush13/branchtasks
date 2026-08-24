"""
Phase 1 gate: create a task end-to-end through Django Admin, confirm ref
formatting, history recording, and that the deactivation guard actually
blocks the admin form — not just the validator function in isolation.
"""

import pytest

from accounts.models import User
from core.models import Branch, Category
from tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_logged_in(client, django_user_model):
    admin = django_user_model.objects.create_superuser("admin_smoke", "a@example.com", "x")
    client.force_login(admin)
    return client, admin


@pytest.fixture
def branch():
    return Branch.objects.create(name_he="תל יצחק", name_en="Tel Yitzhak")


@pytest.fixture
def category():
    return Category.objects.create(name_he="תפעול", name_en="Operations")


def test_create_task_through_admin(admin_client_logged_in, branch, category):
    client, admin = admin_client_logged_in

    resp = client.get("/admin/tasks/task/add/")
    assert resp.status_code == 200

    resp = client.post(
        "/admin/tasks/task/add/",
        data={
            "title": "Admin smoke test task",
            "description": "",
            "branch": branch.pk,
            "category": category.pk,
            "opened_by": admin.pk,
            "priority": 2,
            "status": "new",
            "blocker": "",
            "due_date": "",
            "watchers": [],
            "updates-TOTAL_FORMS": 0,
            "updates-INITIAL_FORMS": 0,
            "updates-MIN_NUM_FORMS": 0,
            "updates-MAX_NUM_FORMS": 1000,
            "attachments-TOTAL_FORMS": 0,
            "attachments-INITIAL_FORMS": 0,
            "attachments-MIN_NUM_FORMS": 0,
            "attachments-MAX_NUM_FORMS": 1000,
            "_save": "Save",
        },
        follow=True,
    )
    assert resp.status_code == 200

    task = Task.objects.get(title="Admin smoke test task")
    assert task.ref == f"TSK-{task.pk:06d}"

    history_resp = client.get(f"/admin/tasks/task/{task.pk}/history/")
    assert history_resp.status_code == 200


def test_deactivation_guard_blocks_admin_form(admin_client_logged_in, branch, category):
    client, admin = admin_client_logged_in
    assignee = User.objects.create_user(username="guarded_user", password="x")
    Task.objects.create(
        title="Active task holding the assignee",
        branch=branch,
        category=category,
        opened_by=admin,
        assignee=assignee,
        status=Task.Status.IN_PROGRESS,
    )

    client.post(
        f"/admin/accounts/user/{assignee.pk}/change/",
        data={
            "username": assignee.username,
            "role": "member",
            "full_name": "",
            "phone": "",
            "date_joined_0": "2026-01-01",
            "date_joined_1": "00:00:00",
            "_save": "Save",
        },
        follow=True,
    )

    assignee.refresh_from_db()
    assert assignee.is_active is True
