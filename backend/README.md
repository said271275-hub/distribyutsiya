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
`apps/logistics`, `apps/payments` and `apps/audit`. Authentication endpoints
and the login/profile frontend flow are implemented; catalog, ordering and
dispatch interfaces remain out of scope.

## Authentication

- Shop owners register with a phone number, one-time SMS code and password at
  `POST /api/auth/register/otp/` and `POST /api/auth/register/`.
- Shop-owner and employee login are separate: `/api/auth/login/` and
  `/api/auth/staff/login/`. Employee accounts are created through Django
  Admin; there is no public staff-registration endpoint.
- Access JWTs last 10 minutes and are returned in the response body. Rotating
  refresh JWTs are stored only in an HttpOnly, SameSite cookie at
  `/api/auth/refresh/`; logout blacklists the refresh token. Unsafe auth
  requests require the CSRF token from `GET /api/auth/csrf/`.
- OTP delivery is selected with the `OTP_PROVIDER` dotted import path. The
  development provider does not send SMS; when `DEV_OTP_ENABLED=True`, it
  accepts the `DEV_OTP_CODE` value from the environment. This flag defaults to
  false and cannot be enabled when `DEBUG=False`.
- Five failed login attempts block that phone/IP combination for 15 minutes;
  registration OTP sends are limited to three per phone per 15 minutes.
- Account deletion requests are confirmed with the current password. Run
  `python manage.py process_account_deletions` from a daily scheduler to
  anonymize requests whose 30-day recovery period has elapsed. Schedule
  `python manage.py cleanup_auth_records` daily as well.

Set `AUTH_COOKIE_SECURE=True` and use HTTPS outside local development. For
cross-origin deployments, configure trusted CORS origins and CSRF origins
explicitly. Refresh cookies use the configured `AUTH_COOKIE_SAMESITE` policy.

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

Before production: `DEV_OTP_ENABLED=false`, connect `EskizOtpProvider`.
