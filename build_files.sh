#!/bin/bash
set -e
# Vercel's build image ships a uv-managed Python (PEP 668
# externally-managed-environment) — this build container is throwaway,
# so overriding that guard here is safe.
pip install --break-system-packages -r requirements.txt
python manage.py collectstatic --noinput
