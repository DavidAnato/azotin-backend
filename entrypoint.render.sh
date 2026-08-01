#!/bin/sh
# Entrypoint Render — migrate + collectstatic + gunicorn.
# Le seed n'est PAS lancé au démarrage : utiliser un one-off Shell :
#   python manage.py seeddata
#   python manage.py seeddata --reset
# Ou définir RUN_SEED=1 temporairement (non recommandé en prod permanente).
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "${RUN_SEED:-0}" = "1" ]; then
  echo "RUN_SEED=1 — seeddata..."
  python manage.py seeddata
fi

PORT="${PORT:-8000}"
echo "Starting Gunicorn on 0.0.0.0:${PORT}..."
exec gunicorn --bind "0.0.0.0:${PORT}" --workers "${WEB_CONCURRENCY:-2}" jobhub_api.wsgi:application
