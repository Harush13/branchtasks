"""
Phase 4 regression guard for §10: physical Tailwind properties (ml-/mr-/
pl-/pr-) silently break RTL and won't fail any other test, so this greps
every template source directly. Also confirms rendered pages actually carry
dir="rtl" (§10.1).
"""

import re
from pathlib import Path

import pytest
from django.test import Client

from tasks.models import Task

pytestmark = pytest.mark.django_db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Word-boundary class names only — deliberately excludes ms-/me-/ps-/pe-
# (the logical properties §10.1 requires) and unrelated tokens like "mr-3"
# inside e.g. a data attribute would still correctly match and fail, which
# is the point.
_FORBIDDEN = re.compile(r'class="[^"]*\b(ml|mr|pl|pr)-\d')


def logged_in(user):
    client = Client()
    client.force_login(user)
    return client


def test_no_physical_direction_classes_in_templates():
    offenders = []
    for path in TEMPLATES_DIR.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if _FORBIDDEN.search(text):
            offenders.append(str(path.relative_to(TEMPLATES_DIR)))
    assert not offenders, f"Physical ml-/mr-/pl-/pr- classes found in: {offenders}"


def test_login_page_is_rtl():
    resp = Client().get("/login/")
    assert 'dir="rtl"' in resp.content.decode()


def test_task_list_page_is_rtl(member):
    resp = logged_in(member).get("/tasks/")
    assert 'dir="rtl"' in resp.content.decode()


def test_ref_is_wrapped_ltr_on_detail_page(member, branch, category):
    task = Task.objects.create(title="Fix", branch=branch, category=category, opened_by=member)
    resp = logged_in(member).get(f"/tasks/{task.ref}/")
    body = resp.content.decode()
    assert re.search(rf'<span dir="ltr"[^>]*>{re.escape(task.ref)}</span>', body)
