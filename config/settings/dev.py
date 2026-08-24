"""
Local development settings. SQLite, DEBUG on, console email backend.

Docker Compose + Postgres 16 is the production target (see docker-compose.yml,
config/settings/prod.py) but neither Docker nor Postgres is installed on this
dev machine, so local development runs on SQLite instead. Everything in the
spec ported cleanly except the `he-IL-x-icu` Hebrew collation (§10.4), which
has no SQLite equivalent — see the engine-aware sort helper noted in
tasks/selectors.py once Phase 2 adds it. Re-verify on real Postgres in Phase 7.
"""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = env.bool("DJANGO_DEBUG", default=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
