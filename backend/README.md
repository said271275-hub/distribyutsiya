# Backend

Django REST Framework API. The development server exposes the API at
`http://localhost:8000/api/`; OpenAPI and Swagger UI are at
`/api/schema/` and `/api/docs/`.

## Run locally

From the project root, create `.env` from `.env.example`, then start PostgreSQL
with Docker Compose:

```powershell
Copy-Item .env.example .env
docker compose up -d db
```

In a second PowerShell window:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:POSTGRES_HOST = "localhost"
python manage.py migrate
python manage.py runserver
```

The API checks endpoint is `GET /api/health/`. Business models are grouped
under `apps/accounts`, `apps/companies`, `apps/catalog`, `apps/orders`,
`apps/logistics`, `apps/payments` and `apps/audit`. No login endpoints or
frontend pages are implemented yet.

## Demo data and tests

After applying migrations, load idempotent local demo data:

```powershell
python manage.py seed_demo
```

Run the test suite without a local PostgreSQL server by using the in-memory
SQLite test settings:

```powershell
$env:DJANGO_SECRET_KEY = "local-test-only"
python manage.py test apps.core --settings=config.test_settings
```

The approved ERD and endpoint proposal are in
[`../docs/00_umumiy_kontekst.md`](../docs/00_umumiy_kontekst.md) and
[`../docs/01_erd_va_api_sxemasi.md`](../docs/01_erd_va_api_sxemasi.md).

## Security and deployment

The `.env.example` values are strictly for local development. Set a unique,
strong `DJANGO_SECRET_KEY`, production hosts and HTTPS-related settings before
deploying. Keep `.env` out of source control. Do not use Django's development
server in production.
