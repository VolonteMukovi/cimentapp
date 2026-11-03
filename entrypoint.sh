#!/bin/bash

set -e

source /.venv/bin/activate

echo "Ensure media and upload temp directories exist..."
mkdir -p /cimentapp/media /cimentapp/tmp
if [ -d /media_legacy ]; then
  echo "Restore existing host media into persistent storage..."
  cp -an /media_legacy/. /cimentapp/media/
fi

echo "Waiting for MySQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "Apply migrations..."
python manage.py migrate

echo "Rassemblement des fichiers statiques..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec gunicorn config.wsgi:application -c /cimentapp/gunicorn.conf.py
