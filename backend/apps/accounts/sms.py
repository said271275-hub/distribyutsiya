import logging
from typing import Protocol

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SMSProvider(Protocol):
    def send(self, phone: str, message: str) -> None: ...


class MockSMSProvider:
    def send(self, phone: str, message: str) -> None:
        logger.warning("Mock SMS to %s: %s", phone, message)


def get_sms_provider() -> SMSProvider:
    provider_path = settings.SMS_PROVIDER_CLASS
    if not provider_path:
        raise ImproperlyConfigured("SMS_PROVIDER_CLASS sozlanmagan.")
    provider_class = import_string(provider_path)
    return provider_class()
