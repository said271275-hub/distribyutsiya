import os
import re
import urllib.parse
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
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = [
        "distribyutsiya-backend.onrender.com",
        "localhost",
        "127.0.0.1",
        ".onrender.com",
    ]

if DJANGO_ENV == "production" and DEBUG:
    raise ImproperlyConfigured("DJANGO_ENV=production bo‘lganda DJANGO_DEBUG=False bo‘lishi kerak.")

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    parsed_db = urllib.parse.urlparse(database_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed_db.path.lstrip("/"),
            "USER": parsed_db.username or "",
            "PASSWORD": parsed_db.password or "",
            "HOST": parsed_db.hostname or "",
            "PORT": str(parsed_db.port or 5432),
            "CONN_MAX_AGE": 60,
        }
    }
else:
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

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))

CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL")
if CLOUDINARY_URL:
    if "cloudinary_storage" not in INSTALLED_APPS:
        INSTALLED_APPS.insert(INSTALLED_APPS.index("django.contrib.staticfiles"), "cloudinary_storage")
    if "cloudinary" not in INSTALLED_APPS:
        INSTALLED_APPS.append("cloudinary")
    CLOUDINARY_STORAGE = {
        "CLOUDINARY_URL": CLOUDINARY_URL,
    }
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
for origin in [
    "https://distribyutsiya.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]:
    if origin not in CORS_ALLOWED_ORIGINS:
        if origin.startswith("https://") or DEBUG:
            CORS_ALLOWED_ORIGINS.append(origin)

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
for origin in [
    "https://distribyutsiya-backend.onrender.com",
    "https://distribyutsiya.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]:
    if origin not in CSRF_TRUSTED_ORIGINS:
        if origin.startswith("https://") or DEBUG:
            CSRF_TRUSTED_ORIGINS.append(origin)

if render_hostname:
    render_origin = f"https://{render_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

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
SESSION_COOKIE_HTTPONLY = True
AUTH_LOGIN_MAX_FAILURES = 5
AUTH_LOGIN_BLOCK_MINUTES = 15
AUTH_OTP_TTL_MINUTES = 5
AUTH_OTP_SEND_LIMIT = 3
AUTH_OTP_SEND_WINDOW_MINUTES = 15
AUTH_OTP_MAX_FAILURES = 5
OTP_PROVIDER = os.environ.get("OTP_PROVIDER", "")
DEV_OTP_ENABLED = env_bool("DEV_OTP_ENABLED", False)
DEV_OTP_CODE = os.environ.get("DEV_OTP_CODE", "")
ESKIZ_EMAIL = os.environ.get("ESKIZ_EMAIL", "")
ESKIZ_PASSWORD = os.environ.get("ESKIZ_PASSWORD", "")
ESKIZ_FROM = os.environ.get("ESKIZ_FROM", "")
if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
    ESKIZ_EMAIL = ESKIZ_EMAIL or "placeholder@example.com"
    ESKIZ_PASSWORD = ESKIZ_PASSWORD or "placeholder_password"
    ESKIZ_FROM = ESKIZ_FROM or "4546"
    OTP_PROVIDER = OTP_PROVIDER or "apps.accounts.sms.EskizOtpProvider"

DEV_STAFF_PASSWORD = os.environ.get("DEV_STAFF_PASSWORD", "")
if DEV_STAFF_PASSWORD and (not DEBUG or not DEV_OTP_ENABLED):
    raise ImproperlyConfigured(
        "DEV_STAFF_PASSWORD faqat DJANGO_DEBUG=True va DEV_OTP_ENABLED=True bo‘lganda ishlaydi."
    )
if not DEBUG and DEV_OTP_ENABLED:
    raise ImproperlyConfigured("DEV_OTP_ENABLED production rejimida yoqilishi mumkin emas.")
if DEV_OTP_ENABLED and not re.fullmatch(r"\d{6}", DEV_OTP_CODE):
    raise ImproperlyConfigured("DEV_OTP_ENABLED uchun DEV_OTP_CODE 6 xonali bo‘lishi kerak.")
if not DEBUG:
    if OTP_PROVIDER != "apps.accounts.sms.EskizOtpProvider":
        raise ImproperlyConfigured(
            "Production muhitida OTP_PROVIDER EskizOtpProvider bo‘lishi kerak."
        )
    if not ESKIZ_EMAIL or not ESKIZ_PASSWORD or not ESKIZ_FROM:
        raise ImproperlyConfigured(
            "Production muhitida ESKIZ_EMAIL, ESKIZ_PASSWORD va ESKIZ_FROM sozlanishi kerak."
        )
    if len(SECRET_KEY) < 20 or SECRET_KEY.lower().startswith(("change-me", "replace-me")):
        raise ImproperlyConfigured(
            "Production muhitida kamida 20 belgili yangi DJANGO_SECRET_KEY kerak."
        )
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "Production muhitida DJANGO_ALLOWED_HOSTS aniq domenlar bilan sozlanishi kerak."
        )
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            "Production muhitida DJANGO_CSRF_TRUSTED_ORIGINS HTTPS manzillari bilan sozlanishi kerak."
        )
    if not all(origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured(
            "Production muhitidagi CSRF ishonchli manzillari HTTPS bo‘lishi kerak."
        )
    if not all(origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS):
        raise ImproperlyConfigured(
            "Production muhitidagi CORS manzillari HTTPS bo‘lishi kerak."
        )
    if not database_url:
        if not os.environ.get("POSTGRES_DB") or not os.environ.get("POSTGRES_USER"):
            raise ImproperlyConfigured(
                "Production muhitida POSTGRES_DB va POSTGRES_USER aniq ko‘rsatilishi kerak."
            )
        if not os.environ.get("POSTGRES_PASSWORD"):
            raise ImproperlyConfigured(
                "Production muhitida POSTGRES_PASSWORD bo‘sh bo‘lishi mumkin emas."
            )

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
CSRF_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"
SESSION_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"

SPECTACULAR_SETTINGS = {
    "TITLE": "Distribyutsiya API",
    "DESCRIPTION": "Ichimliklar buyurtmasi va yetkazib berish API.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", not DEBUG)
SECURE_HSTS_SECONDS = int(
    os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured("Production muhitida HTTPS yo‘naltirishi yoqilgan bo‘lishi kerak.")
    if not (AUTH_COOKIE_SECURE and SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE):
        raise ImproperlyConfigured("Production muhitida barcha autentifikatsiya cookie’lari Secure bo‘lishi kerak.")
    if AUTH_COOKIE_SAMESITE.lower() not in {"lax", "strict", "none"}:
        raise ImproperlyConfigured(
            "Production muhitida AUTH_COOKIE_SAMESITE Lax, Strict yoki None bo‘lishi kerak."
        )
    if SECURE_HSTS_SECONDS < 31536000:
        raise ImproperlyConfigured(
            "Production muhitida HSTS kamida 31536000 soniya qilib sozlanishi kerak."
        )
    if not database_url and DATABASES["default"]["HOST"].strip().lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ImproperlyConfigured(
            "Ushbu production sozlamasida PostgreSQL faqat mahalliy manzilda bo‘lishi kerak."
        )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
