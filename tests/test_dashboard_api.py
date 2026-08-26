"""
Phase 6 gate (spec §6/§8): GET /api/dashboard/summary and
GET /api/dashboard/breakdown — manager/admin only, like every other
dashboard surface (§5).
"""

import pytest

from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


class TestDashboardSummaryPermissions:
    def test_member_forbidden(self, member_client):
        resp = member_client.get("/api/dashboard/summary")
        assert resp.status_code == 403

    def test_manager_allowed(self, manager_client):
        resp = manager_client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        assert set(resp.json()) == {"open", "closed", "overdue", "urgent"}

    def test_admin_allowed(self, admin_client):
        assert admin_client.get("/api/dashboard/summary").status_code == 200

    def test_anonymous_forbidden(self, api_client):
        resp = api_client.get("/api/dashboard/summary")
        assert resp.status_code in (401, 403)


class TestDashboardBreakdown:
    def test_member_forbidden(self, member_client):
        resp = member_client.get("/api/dashboard/breakdown", {"by": "branch"})
        assert resp.status_code == 403

    def test_manager_can_read_each_dimension(
        self, manager_client, branch, category, opener, member
    ):
        make_task(branch, category, opener, assignee=member)
        for dim in ("branch", "category", "priority", "status", "assignee"):
            resp = manager_client.get("/api/dashboard/breakdown", {"by": dim})
            assert resp.status_code == 200, dim
            assert isinstance(resp.json(), list)

    def test_unknown_dimension_is_400(self, manager_client):
        resp = manager_client.get("/api/dashboard/breakdown", {"by": "nonsense"})
        assert resp.status_code == 400

    def test_missing_dimension_is_400(self, manager_client):
        resp = manager_client.get("/api/dashboard/breakdown")
        assert resp.status_code == 400
