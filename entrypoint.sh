#!/bin/sh
# Entrypoint Docker / production.
# Variables optionnelles :
#   ALLOW_FLUSH=1   — flush DB (démons éphémères uniquement, JAMAIS en prod)
#   SKIP_SEED=1     — désactive le seed automatique
#   PORT            — port d'écoute (défaut 8000 ; Render injecte $PORT)
set -e

if [ "${ALLOW_FLUSH:-0}" = "1" ]; then
  echo "ALLOW_FLUSH=1 — flush de la base (démo éphémère uniquement)..."
  python manage.py flush --noinput
fi

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
exec gunicorn --bind "0.0.0.0:${PORT}" azobatin_api.wsgi:application
