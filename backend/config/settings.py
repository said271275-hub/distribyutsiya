import os
import re
from datetime import time
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the environment.")

DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    "apps.core",
    "apps.accounts",
    "apps.companies",
    "apps.catalog",
    "apps.orders",
    "apps.logistics",
    "apps.payments",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.CompanyTenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "distribyutsiya"),
        "USER": os.environ.get("POSTGRES_USER", "distribyutsiya"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.CookieAwareJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "apps.core.filters.CompanyTenantFilterBackend",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", not DEBUG)
AUTH_COOKIE_SAMESITE = os.environ.get("AUTH_COOKIE_SAMESITE", "Lax")
if AUTH_COOKIE_SAMESITE.lower() == "none" and not AUTH_COOKIE_SECURE:
    raise ImproperlyConfigured("SameSite=None refresh cookies require AUTH_COOKIE_SECURE=True.")
AUTH_COOKIE_NAME = "distribyutsiya_refresh"
AUTH_COOKIE_PATH = "/api/auth/"
AUTH_COOKIE_HTTPONLY = True
AUTH_COOKIE_MAX_AGE = int(SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
AUTH_LOGIN_MAX_FAILURES = 5
AUTH_LOGIN_BLOCK_MINUTES = 15
AUTH_OTP_TTL_MINUTES = 5
AUTH_OTP_SEND_LIMIT = 3
AUTH_OTP_SEND_WINDOW_MINUTES = 15
AUTH_OTP_MAX_FAILURES = 5
OTP_PROVIDER = os.environ.get("OTP_PROVIDER", "")
DEV_OTP_ENABLED = env_bool("DEV_OTP_ENABLED", False)
DEV_OTP_CODE = os.environ.get("DEV_OTP_CODE", "")
DEV_STAFF_PASSWORD = os.environ.get("DEV_STAFF_PASSWORD", "")
if DEV_STAFF_PASSWORD and (not DEBUG or not DEV_OTP_ENABLED):
    raise ImproperlyConfigured(
        "DEV_STAFF_PASSWORD faqat DJANGO_DEBUG=True va DEV_OTP_ENABLED=True bo‘lganda ishlaydi."
    )
if not DEBUG and DEV_OTP_ENABLED:
    raise ImproperlyConfigured("DEV_OTP_ENABLED production rejimida yoqilishi mumkin emas.")
if DEV_OTP_ENABLED and not re.fullmatch(r"\d{6}", DEV_OTP_CODE):
    raise ImproperlyConfigured("DEV_OTP_ENABLED uchun DEV_OTP_CODE 6 xonali bo‘lishi kerak.")

ROUTING_EXTERNAL_ENABLED = env_bool("ROUTING_EXTERNAL_ENABLED", DEBUG)
OSRM_BASE_URL = os.environ.get(
    "OSRM_BASE_URL",
    "https://router.project-osrm.org" if DEBUG else "",
).rstrip("/")
ROUTING_TIMEOUT_SECONDS = int(os.environ.get("ROUTING_TIMEOUT_SECONDS", "5"))
ROUTE_START_TIME = time.fromisoformat(os.environ.get("ROUTE_START_TIME", "08:00"))
ETA_WINDOW_MINUTES = int(os.environ.get("ETA_WINDOW_MINUTES", "45"))
TRIP_CLUSTER_RADIUS_KM = float(os.environ.get("TRIP_CLUSTER_RADIUS_KM", "8"))
if ROUTING_TIMEOUT_SECONDS < 1 or ETA_WINDOW_MINUTES < 1 or TRIP_CLUSTER_RADIUS_KM <= 0:
    raise ImproperlyConfigured(
        "Routing timeout, ETA window va trip cluster radius musbat bo‘lishi kerak."
    )
if ROUTING_EXTERNAL_ENABLED and not OSRM_BASE_URL:
    raise ImproperlyConfigured(
        "ROUTING_EXTERNAL_ENABLED=True bo‘lsa OSRM_BASE_URL sozlanishi kerak."
    )
if (
    not DEBUG
    and ROUTING_EXTERNAL_ENABLED
    and "router.project-osrm.org" in OSRM_BASE_URL.lower()
):
    raise ImproperlyConfigured(
        "Production muhitida ommaviy OSRM demo serveridan foydalanmang."
    )

CORS_ALLOW_CREDENTIALS = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

SPECTACULAR_SETTINGS = {
    "TITLE": "Distribyutsiya API",
    "DESCRIPTION": "Ichimliklar buyurtmasi va yetkazib berish API.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES")
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES")
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
