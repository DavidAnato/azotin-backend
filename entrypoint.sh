#!/bin/sh
# Single-instance VPS startup: migrate, collect static assets, then serve ASGI.
set -eu

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-azobatin_api.settings.production}"

python manage.py migrate --noinput
python manage.py collectstatic --noinput

PORT="${PORT:-8000}"
echo "Starting ASGI server on 0.0.0.0:${PORT}..."
exec uvicorn azobatin_api.asgi:application \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers \
  --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
