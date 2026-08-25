"""
Fixtures shared by every test module. Phases 0-2 had each file redeclare
branch/category/member/manager/admin_user identically; Phase 3 adds several
API test modules that need the same users plus an authenticated client, so
this is the point past which duplicating them stops being harmless.
"""

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from core.models import Branch, Category


@pytest.fixture
def branch():
    return Branch.objects.create(name_he="תל יצחק", name_en="Tel Yitzhak")


@pytest.fixture
def category():
    return Category.objects.create(name_he="תפעול", name_en="Operations")


@pytest.fixture
def opener():
    return User.objects.create_user(username="opener", password="x")


@pytest.fixture
def member():
    return User.objects.create_user(username="member1", password="x", role=User.Role.MEMBER)


@pytest.fixture
def manager():
    return User.objects.create_user(username="manager1", password="x", role=User.Role.MANAGER)


@pytest.fixture
def admin_user():
    return User.objects.create_user(username="admin1", password="x", role=User.Role.ADMIN)


@pytest.fixture
def api_client():
    """Unauthenticated DRF client — for asserting the anonymous-access boundary."""
    return APIClient()


def _logged_in_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def member_client(member):
    return _logged_in_client(member)


@pytest.fixture
def manager_client(manager):
    return _logged_in_client(manager)


@pytest.fixture
def admin_client(admin_user):
    return _logged_in_client(admin_user)
