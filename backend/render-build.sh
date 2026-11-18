#!/usr/bin/env bash
# exit on error
set -o errexit

export ESKIZ_EMAIL="${ESKIZ_EMAIL:-placeholder@example.com}"
export ESKIZ_PASSWORD="${ESKIZ_PASSWORD:-placeholder_password}"
export ESKIZ_FROM="${ESKIZ_FROM:-4546}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-distribyutsiya-backend.onrender.com,localhost,127.0.0.1}"
export DJANGO_CORS_ALLOWED_ORIGINS="${DJANGO_CORS_ALLOWED_ORIGINS:-https://distribyutsiya.vercel.app}"
export DJANGO_CSRF_TRUSTED_ORIGINS="${DJANGO_CSRF_TRUSTED_ORIGINS:-https://distribyutsiya-backend.onrender.com,https://distribyutsiya.vercel.app}"
export AUTH_COOKIE_SAMESITE="${AUTH_COOKIE_SAMESITE:-None}"

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_custom_accounts
