#!/bin/sh
# Entrypoint Docker / production — chemin sûr par défaut (pas de flush).
# Variables optionnelles :
#   ALLOW_FLUSH=1   — flush DB (démons éphémères uniquement, JAMAIS en prod)
#   RUN_SEED=1      — exécute seeddata après migrate
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

if [ "${RUN_SEED:-0}" = "1" ]; then
  echo "RUN_SEED=1 — chargement des données de démonstration (seeddata)..."
  python manage.py seeddata
fi

PORT="${PORT:-8000}"
echo "Starting Gunicorn on 0.0.0.0:${PORT}..."
exec gunicorn --bind "0.0.0.0:${PORT}" jobhub_api.wsgi:application
