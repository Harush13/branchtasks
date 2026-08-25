"""
Phase 3: §6's "PATCH must reject a status key" rule, plus legal/illegal
transitions and blocker enforcement exercised over HTTP — the state-machine
rules themselves are already covered by tests/test_services.py.
"""

import pytest

from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


def test_patch_with_status_key_rejected(member_client, member, branch, category):
    task = make_task(branch, category, member)
    resp = member_client.patch(f"/api/tasks/{task.ref}", {"status": "done"})
    assert resp.status_code == 400
    assert "status" in resp.json()


def test_legal_transition_via_status_endpoint(member_client, member, branch, category):
    task = make_task(branch, category, member)
    resp = member_client.post(f"/api/tasks/{task.ref}/status", {"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_illegal_transition_rejected(member_client, member, branch, category):
    task = make_task(branch, category, member)  # new
    resp = member_client.post(f"/api/tasks/{task.ref}/status", {"status": "new"})
    assert resp.status_code == 400


def test_waiting_without_blocker_rejected(member_client, member, branch, category):
    task = make_task(branch, category, member)
    resp = member_client.post(f"/api/tasks/{task.ref}/status", {"status": "waiting"})
    assert resp.status_code == 400


def test_waiting_with_blocker_accepted(member_client, member, branch, category):
    task = make_task(branch, category, member)
    resp = member_client.post(
        f"/api/tasks/{task.ref}/status", {"status": "waiting", "blocker": "waiting on parts"}
    )
    assert resp.status_code == 200
    assert resp.json()["blocker"] == "waiting on parts"
