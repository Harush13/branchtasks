"""Phase 7 gate: GET /api/dashboard/kpis — manager/admin only (§5, §9)."""

import pytest

pytestmark = pytest.mark.django_db


class TestDashboardKpis:
    def test_member_forbidden(self, member_client):
        assert member_client.get("/api/dashboard/kpis").status_code == 403

    def test_manager_gets_all_four_kpis(self, manager_client):
        resp = manager_client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        assert set(resp.json()) == {
            "avg_days_to_close_90d",
            "opened_vs_closed_by_month",
            "on_time_closure_rate_pct",
            "performance_by_branch",
        }

    def test_anonymous_forbidden(self, api_client):
        assert api_client.get("/api/dashboard/kpis").status_code in (401, 403)
