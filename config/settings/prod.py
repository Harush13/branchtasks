"""
Production settings: PostgreSQL 16 via DATABASE_URL, DEBUG off. Served by
gunicorn behind nginx per docker-compose.yml. Unvalidated on this dev machine
(no Docker/Postgres installed) — exercise this file for real at Phase 7.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
