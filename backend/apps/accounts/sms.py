from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class OTPProvider(Protocol):
    def generate_code(self) -> str: ...

    def send(self, phone: str, message: str) -> None: ...


class DevOtpProvider:
    def generate_code(self) -> str:
        if not settings.DEV_OTP_ENABLED:
            raise ImproperlyConfigured("Dev OTP faqat DEV_OTP_ENABLED=True bo‘lganda ishlaydi.")
        return settings.DEV_OTP_CODE

    def send(self, phone: str, message: str) -> None:
        return None


def get_otp_provider() -> OTPProvider:
    provider_path = settings.OTP_PROVIDER
    if not provider_path:
        raise ImproperlyConfigured("OTP_PROVIDER sozlanmagan.")
    provider_class = import_string(provider_path)
    return provider_class()
