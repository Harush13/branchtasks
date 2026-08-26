"""
Phase 7 gate: GET /api/tasks/export — same visibility rule as GET /api/tasks
(§5: any authenticated member, not manager-only), filtered the same way,
returned as CSV instead of JSON.
"""

import pytest

from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


class TestTaskExport:
    def test_member_can_export(self, member_client, branch, category, opener):
        make_task(branch, category, opener)
        resp = member_client.get("/api/tasks/export")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "attachment" in resp["Content-Disposition"]

    def test_anonymous_forbidden(self, api_client):
        resp = api_client.get("/api/tasks/export")
        assert resp.status_code in (401, 403)

    def test_csv_contains_header_and_row(self, member_client, branch, category, opener):
        task = make_task(branch, category, opener)
        resp = member_client.get("/api/tasks/export")
        body = resp.content.decode("utf-8-sig")
        lines = body.strip().splitlines()
        assert lines[0].split(",")[0] == "ref"
        assert any(task.ref in line for line in lines[1:])

    def test_respects_status_filter(self, member_client, branch, category, opener):
        make_task(branch, category, opener, status=Task.Status.NEW)
        done = make_task(branch, category, opener)
        done.status = Task.Status.DONE
        from django.utils import timezone

        done.completed_at = timezone.now()
        done.save()

        resp = member_client.get("/api/tasks/export", {"status": "done"})
        body = resp.content.decode("utf-8-sig")

        assert done.ref in body
        assert body.count("TSK-") == 1

    def test_export_does_not_collide_with_task_detail_route(
        self, member_client, branch, category, opener
    ):
        """`export` must resolve to the export action, not be treated as a
        task `ref` by the detail route's `[^/]+` lookup regex."""
        resp = member_client.get("/api/tasks/export")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"

    @pytest.mark.parametrize("dangerous_title", ["=cmd|'/c calc'!A1", "+1+1", "-2+3", "@SUM(1)"])
    def test_formula_like_title_is_neutralized(
        self, member_client, branch, category, opener, dangerous_title
    ):
        """CSV Formula Injection (CWE-1236): a title starting with =/+/-/@
        must not reach the file as a live formula for Excel/Sheets to run."""
        make_task(branch, category, opener, title=dangerous_title)
        resp = member_client.get("/api/tasks/export")
        body = resp.content.decode("utf-8-sig")
        assert f"'{dangerous_title}" in body
        assert f",{dangerous_title}," not in body
