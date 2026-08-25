"""
Phase 3: §5 says session auth with cookies, not JWT — these tests exercise
the real Django login flow (Django's test Client, which carries cookies),
not the force_authenticate shortcut the other API test files use.
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_login_sets_session_cookie(member):
    client = Client()
    resp = client.post("/api/auth/login", {"username": member.username, "password": "x"})
    assert resp.status_code == 200
    assert resp.wsgi_request.session.get("_auth_user_id") is not None


def test_login_wrong_password_rejected(member):
    client = Client()
    resp = client.post("/api/auth/login", {"username": member.username, "password": "wrong"})
    assert resp.status_code == 401


def test_logout_ends_session(member):
    client = Client()
    client.post("/api/auth/login", {"username": member.username, "password": "x"})
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204
    resp2 = client.get("/api/tasks")
    assert resp2.status_code in (401, 403)


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/tasks"),
        ("get", "/api/meta"),
        ("get", "/api/notifications"),
    ],
)
def test_anonymous_access_denied(api_client, method, path):
    resp = getattr(api_client, method)(path)
    assert resp.status_code in (401, 403)
