#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Railway terminates HTTPS before forwarding to this application.
export DJANGO_DEBUG="${DJANGO_DEBUG:-0}"
export TRUST_HTTPS_PROXY="${TRUST_HTTPS_PROXY:-1}"
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8080}" --workers 1 --access-logfile - --error-logfile -
