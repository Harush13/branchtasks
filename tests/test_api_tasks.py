"""
Phase 3: §6's GET /api/tasks query parameters, default ordering, the
ordering whitelist, and pagination defaults/cap.
"""

import datetime

import pytest
from django.utils import timezone

from core.models import Branch, Category
from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


@pytest.fixture
def second_branch():
    return Branch.objects.create(name_he="חיפה", name_en="Haifa")


@pytest.fixture
def second_category():
    return Category.objects.create(name_he="תחזוקה", name_en="Maintenance")


class TestListFiltering:
    def test_filter_by_branch(self, member_client, branch, second_branch, category, member):
        t1 = make_task(branch, category, member)
        make_task(second_branch, category, member)
        resp = member_client.get("/api/tasks", {"branch": branch.id})
        refs = [row["ref"] for row in resp.json()["results"]]
        assert refs == [t1.ref]

    def test_filter_by_repeatable_status(self, member_client, branch, category, member):
        t1 = make_task(branch, category, member, status=Task.Status.NEW)
        t2 = make_task(branch, category, member, status=Task.Status.WAITING, blocker="stuck")
        make_task(branch, category, member, status=Task.Status.DONE, completed_at=timezone.now())
        resp = member_client.get("/api/tasks", {"status": ["new", "waiting"]})
        refs = {row["ref"] for row in resp.json()["results"]}
        assert refs == {t1.ref, t2.ref}

    def test_overdue_filter(self, member_client, branch, category, member):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        overdue = make_task(branch, category, member, due_date=yesterday)
        make_task(branch, category, member, due_date=timezone.localdate())
        resp = member_client.get("/api/tasks", {"overdue": "1"})
        refs = [row["ref"] for row in resp.json()["results"]]
        assert refs == [overdue.ref]

    def test_free_text_search(self, member_client, branch, category, member):
        target = make_task(branch, category, member, title="Replace the water heater")
        make_task(branch, category, member, title="Order napkins")
        resp = member_client.get("/api/tasks", {"q": "water heater"})
        refs = [row["ref"] for row in resp.json()["results"]]
        assert refs == [target.ref]

    def test_default_ordering_is_priority_desc_due_date_asc(
        self, member_client, branch, category, member
    ):
        low = make_task(branch, category, member, priority=Task.Priority.LOW)
        urgent = make_task(branch, category, member, priority=Task.Priority.URGENT)
        normal = make_task(branch, category, member, priority=Task.Priority.NORMAL)
        resp = member_client.get("/api/tasks")
        refs = [row["ref"] for row in resp.json()["results"]]
        assert refs.index(urgent.ref) < refs.index(normal.ref) < refs.index(low.ref)

    def test_ordering_whitelist_rejects_unknown_field(
        self, member_client, branch, category, member
    ):
        make_task(branch, category, member)
        resp = member_client.get("/api/tasks", {"ordering": "opened_by__username"})
        assert resp.status_code == 400

    def test_ordering_whitelist_accepts_known_field(self, member_client, branch, category, member):
        make_task(branch, category, member)
        resp = member_client.get("/api/tasks", {"ordering": "-created_at"})
        assert resp.status_code == 200


class TestPagination:
    def test_default_page_size_is_25(self, member_client, branch, category, member):
        for _ in range(30):
            make_task(branch, category, member)
        resp = member_client.get("/api/tasks")
        body = resp.json()
        assert len(body["results"]) == 25
        assert body["count"] == 30

    def test_page_size_capped_at_100(self, member_client, branch, category, member):
        # Plain create() per row, not bulk_create — Task.save() backfills the
        # unique `ref` per row; bulk_create would insert 110 blank refs and
        # trip the unique constraint.
        for i in range(110):
            make_task(branch, category, member, title=f"T{i}")
        resp = member_client.get("/api/tasks", {"page_size": 500})
        assert len(resp.json()["results"]) == 100
