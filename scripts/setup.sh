#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py check
if [ "${1:-}" = "--demo" ]; then .venv/bin/python manage.py seed_demo; fi
