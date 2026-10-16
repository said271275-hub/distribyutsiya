$env:DJANGO_SECRET_KEY = ""
$env:DJANGO_DEBUG = "1"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

$env:POSTGRES_DB = "distribyutsiya"
$env:POSTGRES_USER = "distribyutsiya"
$env:POSTGRES_PASSWORD = ""
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5432"

$env:OTP_PROVIDER = ""
$env:DEV_OTP_ENABLED = "0"
$env:DEV_OTP_CODE = ""
