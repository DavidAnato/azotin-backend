#!/bin/sh
# Entrypoint Render — migrate + collectstatic + seed + gunicorn.
# Désactiver le seed : SKIP_SEED=1
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "${SKIP_SEED:-0}" = "1" ]; then
  echo "SKIP_SEED=1 — seeddata ignoré."
else
  echo "seeddata automatique..."
  python manage.py seeddata
fi

PORT="${PORT:-8000}"
echo "Starting Gunicorn on 0.0.0.0:${PORT}..."
exec gunicorn --bind "0.0.0.0:${PORT}" --workers "${WEB_CONCURRENCY:-2}" jobhub_api.wsgi:application
