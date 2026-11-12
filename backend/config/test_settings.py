import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-for-local-testing-purposes-minimum-50-characters")
os.environ.setdefault("DJANGO_DEBUG", "True")
os.environ.setdefault("OTP_PROVIDER", "apps.accounts.sms.DevOtpProvider")
os.environ.setdefault("DEV_OTP_ENABLED", "True")
os.environ.setdefault("DEV_OTP_CODE", "123456")

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

