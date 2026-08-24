#!/bin/sh
# Runs migrate + collectstatic against the real env vars docker-compose
# injects at container start, then hands off to CMD (gunicorn).
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
