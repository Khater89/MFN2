#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python manage.py check
exec .venv/bin/python manage.py runserver "${DEV_BIND:-127.0.0.1:8000}" --noreload
