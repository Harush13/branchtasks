"""
Phase 4: login page renders, bad credentials rejected, and every task URL
redirects an anonymous visitor to /login/ (§5's session-auth boundary,
exercised over the HTML surface this time — Django's test Client carries
cookies the way a real browser session would).
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_login_page_renders():
    resp = Client().get("/login/")
    assert resp.status_code == 200
    assert 'dir="rtl"' in resp.content.decode()


def test_bad_credentials_rejected(member):
    resp = Client().post("/login/", {"username": member.username, "password": "wrong"})
    assert resp.status_code == 200
    assert b"login" in resp.wsgi_request.path.encode() or resp.context["form"].errors


def test_login_redirects_to_task_list(member):
    resp = Client().post("/login/", {"username": member.username, "password": "x"})
    assert resp.status_code == 302
    assert resp.url == "/"


@pytest.mark.parametrize(
    "path",
    ["/tasks/", "/tasks/my/", "/tasks/new/"],
)
def test_anonymous_redirected_to_login(path):
    resp = Client().get(path)
    assert resp.status_code == 302
    assert resp.url.startswith("/login/")
