#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# delete all jobs
python manage.py shell -c "from app_job.models import Job; Job.objects.all().delete()"

# make migrations
python manage.py makemigrations

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "seed superuser"
python manage.py seed_superuser

echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8000 jobhub_api.wsgi:application

#echo "Starting Django development server..."
#python manage.py runserver 0.0.0.0:8000