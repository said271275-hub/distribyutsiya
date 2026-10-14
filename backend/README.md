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

The API checks endpoint is `GET /api/health/`. The initial project has no
business models or authentication flows yet.

## Security and deployment

The `.env.example` values are strictly for local development. Set a unique,
strong `DJANGO_SECRET_KEY`, production hosts and HTTPS-related settings before
deploying. Keep `.env` out of source control. Do not use Django's development
server in production.
