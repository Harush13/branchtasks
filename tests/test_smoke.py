"""
Phase 0 sanity checks: settings actually load and the two non-negotiable
knobs from spec §10.2 (store UTC, render Asia/Jerusalem) are set correctly.
Everything else gets real tests once there is real behavior to test.
"""

from django.conf import settings


def test_settings_loaded():
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_timezone_is_utc_storage_jerusalem_display():
    assert settings.USE_TZ is True
    assert settings.TIME_ZONE == "Asia/Jerusalem"


def test_hebrew_is_primary_language():
    assert settings.LANGUAGE_CODE == "he"
