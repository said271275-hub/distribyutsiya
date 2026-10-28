import json
import secrets
import threading
import time
import urllib.error
import urllib.request
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


class SmsProviderError(Exception):
    def __init__(self, code: str, status_code: int | None = None):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class EskizSmsClient:
    _token = ""
    _token_renew_at = 0.0
    _token_email = ""
    _token_lock = threading.Lock()
    _base_url = "https://notify.eskiz.uz/api"
    _timeout_seconds = 5

    def _post(self, path: str, payload: dict | None, token: str = "") -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise SmsProviderError("http_error", error.code) from None
        except (urllib.error.URLError, TimeoutError):
            raise SmsProviderError("network_error") from None
        try:
            result = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise SmsProviderError("invalid_response") from None
        if not isinstance(result, dict):
            raise SmsProviderError("invalid_response")
        return result

    def _login(self) -> str:
        result = self._post(
            "/auth/login",
            {"email": settings.ESKIZ_EMAIL, "password": settings.ESKIZ_PASSWORD},
        )
        token = result.get("data", {}).get("token")
        if not isinstance(token, str) or not token:
            raise SmsProviderError("invalid_auth_response")
        self._token = token
        self._token_email = settings.ESKIZ_EMAIL
        self._token_renew_at = time.monotonic() + (29 * 24 * 60 * 60)
        return token

    def _get_token(self, *, force_refresh: bool = False) -> str:
        with self._token_lock:
            if (
                not force_refresh
                and self._token
                and self._token_email == settings.ESKIZ_EMAIL
                and time.monotonic() < self._token_renew_at
            ):
                return self._token
            if self._token and self._token_email == settings.ESKIZ_EMAIL:
                try:
                    result = self._post("/auth/refresh", None, self._token)
                    token = result.get("data", {}).get("token")
                    if isinstance(token, str) and token:
                        self._token = token
                        self._token_renew_at = time.monotonic() + (29 * 24 * 60 * 60)
                        return token
                except SmsProviderError as error:
                    if error.status_code != 401:
                        raise
            return self._login()

    def send_sms(self, phone: str, message: str) -> None:
        if not settings.ESKIZ_EMAIL or not settings.ESKIZ_PASSWORD or not settings.ESKIZ_FROM:
            raise ImproperlyConfigured(
                "ESKIZ_EMAIL, ESKIZ_PASSWORD va ESKIZ_FROM sozlanishi kerak."
            )
        digits = "".join(character for character in phone if character.isdigit())
        if digits.startswith("998") and len(digits) == 12:
            digits = digits[3:]
        if len(digits) != 9:
            raise SmsProviderError("invalid_phone")

        payload = {
            "mobile_phone": f"998{digits}",
            "message": message,
            "from": settings.ESKIZ_FROM,
        }
        token = self._get_token()
        refreshed = False
        for attempt in range(2):
            try:
                self._post("/message/sms/send", payload, token)
                return
            except SmsProviderError as error:
                if error.status_code == 401 and not refreshed:
                    token = self._get_token(force_refresh=True)
                    refreshed = True
                    continue
                if attempt == 0 and (
                    error.status_code is None or error.status_code >= 500
                ):
                    time.sleep(0.2)
                    token = self._get_token()
                    continue
                raise


_ESKIZ_CLIENT = EskizSmsClient()


class EskizOtpProvider:
    def __init__(self):
        self.client = _ESKIZ_CLIENT

    def generate_code(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def send(self, phone: str, message: str) -> None:
        self.client.send_sms(phone, message)


def get_otp_provider() -> OTPProvider:
    provider_path = settings.OTP_PROVIDER
    if not provider_path:
        raise ImproperlyConfigured("OTP_PROVIDER sozlanmagan.")
    provider_class = import_string(provider_path)
    return provider_class()
