"""ASGI config. Not actively used in v1 (no WebSockets, no async views) but
kept so `runserver`/deployment tooling that expects it works out of the box.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
