"""
Production settings: PostgreSQL 16 via DATABASE_URL, DEBUG off. Served by
gunicorn behind nginx per docker-compose.yml.
"""

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, env

DEBUG = False

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# nginx.conf serves static files in the Docker deployment; serverless
# platforms (Vercel) have no nginx in front, so whitenoise serves
# STATIC_ROOT directly from the WSGI app instead.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# nginx.conf only terminates plain HTTP — it has no TLS server block, so
# forcing HTTPS before a domain + certificate exist (see README's deployment
# runbook for the certbot step) would redirect every request to an
# https:// nothing serves. DJANGO_FORCE_HTTPS defaults True for the steady
# state; the runbook has the operator flip it False only for the brief
# HTTP-only bring-up window.
FORCE_HTTPS = env.bool("DJANGO_FORCE_HTTPS", default=True)
SECURE_SSL_REDIRECT = FORCE_HTTPS
SESSION_COOKIE_SECURE = FORCE_HTTPS
CSRF_COOKIE_SECURE = FORCE_HTTPS
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7 if FORCE_HTTPS else 0
