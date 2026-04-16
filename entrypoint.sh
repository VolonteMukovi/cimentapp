#!/bin/bash

set -e

source /.venv/bin/activate

echo "⏳ Waiting for MySQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "📦 Apply migrations..."
python manage.py migrate

echo "🚀 Starting server..."
exec python manage.py runserver 0.0.0.0:8000