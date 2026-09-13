#!/bin/bash
set -e
# Vercel's build image ships a uv-managed Python (PEP 668
# externally-managed-environment) — this build container is throwaway,
# so overriding that guard here is safe.
pip install --break-system-packages -r requirements.txt

# manage.py's setdefault() only fires when the var is completely unset;
# Vercel can inject DJANGO_SETTINGS_MODULE as an empty string, which
# short-circuits it and Django management prints "No Django settings
# specified." — force it explicitly for this build step instead.
export DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py collectstatic --noinput
