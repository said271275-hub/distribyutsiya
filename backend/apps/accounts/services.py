import hmac
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.accounts.models import (
    DeletionRequest,
    LoginAttempt,
    PhoneOTP,
    PhoneOTPSendWindow,
    User,
)
from apps.audit.models import AuditLog


def normalize_uz_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 9:
        digits = f"998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    raise ValidationError({"phone": "Telefon raqamini +998 XX XXX XX XX formatida kiriting."})


def audit_event(action, *, user=None, company=None, entity_type="User", entity_id=""):
    AuditLog.objects.create(
        actor=user,
        company=company or (user.company if user else None),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or (user.pk if user else "")),
    )


def _otp_digest(code: str) -> str:
    return salted_hmac("accounts.PhoneOTP", code, secret=settings.SECRET_KEY).hexdigest()


def send_registration_otp(phone: str) -> None:
    now = timezone.now()
    if User.objects.filter(phone=phone).exists():
        raise ValidationError({"phone": "Bu telefon raqami allaqachon ro‘yxatdan o‘tgan."})
    from apps.accounts.sms import get_otp_provider

    provider = get_otp_provider()
    code = provider.generate_code()
    with transaction.atomic():
        window, _ = PhoneOTPSendWindow.objects.select_for_update().get_or_create(
            phone=phone,
            defaults={"window_started_at": now, "sent_count": 0},
        )
        if window.window_started_at <= now - timedelta(
            minutes=settings.AUTH_OTP_SEND_WINDOW_MINUTES
        ):
            window.window_started_at = now
            window.sent_count = 0
        if window.sent_count >= settings.AUTH_OTP_SEND_LIMIT:
            raise ValidationError(
                {"phone": "SMS kod yuborish limiti tugadi. Birozdan keyin urinib ko‘ring."}
            )
        window.sent_count += 1
        window.save(update_fields=("window_started_at", "sent_count"))
        PhoneOTP.objects.create(
            phone=phone,
            purpose=PhoneOTP.Purpose.REGISTRATION,
            code_hash=_otp_digest(code),
            expires_at=now + timedelta(minutes=settings.AUTH_OTP_TTL_MINUTES),
        )
    provider.send(phone, f"Ro‘yxatdan o‘tish kodi: {code}")


def consume_registration_otp(phone: str, code: str) -> None:
    invalid_code = False
    with transaction.atomic():
        otp = (
            PhoneOTP.objects.select_for_update()
            .filter(
                phone=phone,
                purpose=PhoneOTP.Purpose.REGISTRATION,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        now = timezone.now()
        if otp is None or otp.expires_at <= now or otp.failed_attempts >= settings.AUTH_OTP_MAX_FAILURES:
            invalid_code = True
        elif not hmac.compare_digest(otp.code_hash, _otp_digest(code)):
            otp.failed_attempts += 1
            if otp.failed_attempts >= settings.AUTH_OTP_MAX_FAILURES:
                otp.consumed_at = now
            otp.save(update_fields=("failed_attempts", "consumed_at"))
            invalid_code = True
        else:
            otp.consumed_at = now
            otp.save(update_fields=("consumed_at",))
    if invalid_code:
        raise ValidationError({"code": "SMS kodi noto‘g‘ri yoki muddati tugagan."})


def register_shop_owner(*, phone: str, code: str, password: str) -> User:
    phone = normalize_uz_phone(phone)
    if User.objects.filter(phone=phone).exists():
        raise ValidationError({"phone": "Bu telefon raqami allaqachon ro‘yxatdan o‘tgan."})
    try:
        password_validation.validate_password(password)
    except DjangoValidationError as error:
        raise ValidationError({"password": list(error.messages)}) from error

    consume_registration_otp(phone, code)
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                phone=phone, password=password, role=User.Role.SHOP_OWNER
            )
    except IntegrityError as error:
        raise ValidationError(
            {"phone": "Bu telefon raqami allaqachon ro‘yxatdan o‘tgan."}
        ) from error
    audit_event("shop_registered", user=user)
    return user


def login_user(*, phone: str, password: str, scope: str, ip_address: str) -> User:
    phone = normalize_uz_phone(phone)
    now = timezone.now()
    error_message = None
    authenticated_user = None
    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(
            phone=phone, ip_address=ip_address, scope=scope
        )
        if attempt.blocked_until and attempt.blocked_until > now:
            error_message = "Kirish vaqtincha bloklangan. Keyinroq qayta urinib ko‘ring."
        else:
            if attempt.blocked_until and attempt.blocked_until <= now:
                attempt.failures = 0
                attempt.blocked_until = None

            user = authenticate(username=phone, password=password)
            valid_role = user is not None and (
                user.role == User.Role.SHOP_OWNER
                if scope == "shop"
                else user.role != User.Role.SHOP_OWNER
            )
            if not valid_role or user.is_blocked or user.is_deleted:
                attempt.failures += 1
                if attempt.failures >= settings.AUTH_LOGIN_MAX_FAILURES:
                    attempt.blocked_until = now + timedelta(
                        minutes=settings.AUTH_LOGIN_BLOCK_MINUTES
                    )
                attempt.save(update_fields=("failures", "blocked_until", "updated_at"))
                audit_event(
                    f"{scope}_login_failed",
                    user=User.objects.filter(phone=phone).first(),
                    entity_type="Login",
                )
                error_message = (
                    "5 ta noto‘g‘ri urinishdan so‘ng kirish 15 daqiqaga bloklandi."
                    if attempt.blocked_until
                    else "Telefon raqami yoki parol noto‘g‘ri."
                )
            else:
                LoginAttempt.objects.filter(
                    phone=phone, ip_address=ip_address, scope=scope
                ).delete()
                user.last_login = now
                user.save(update_fields=("last_login",))
                audit_event(f"{scope}_login_succeeded", user=user, entity_type="Login")
                authenticated_user = user

    if error_message:
        raise AuthenticationFailed(error_message)
    if authenticated_user is None:
        raise AuthenticationFailed("Telefon raqami yoki parol noto‘g‘ri.")
    return authenticated_user


def request_account_deletion(*, user: User, password: str, reason: str, reason_other: str):
    if not user.check_password(password):
        raise ValidationError({"password": "Parol noto‘g‘ri."})
    if reason == DeletionRequest.Reason.OTHER and not reason_other.strip():
        raise ValidationError({"reason_other": "Boshqa sababni yozing."})

    shops = user.shops.all()
    from apps.orders.models import Order
    from apps.payments.models import ShopBalance

    open_orders = Order.objects.filter(shop__in=shops).exclude(
        status__in=(Order.Status.DELIVERED, Order.Status.CANCELLED)
    )
    if open_orders.exists():
        raise ValidationError(
            {"account": "Ochiq buyurtmalar bor. Avval ularni yakunlang yoki bekor qiling."}
        )
    if ShopBalance.objects.filter(shop__in=shops, current_balance__gt=0).exists():
        raise ValidationError(
            {"account": "To‘lanmagan qarz bor. Avval qarzni to‘liq yoping."}
        )

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.deletion_requests.filter(status=DeletionRequest.Status.PENDING).exists():
            raise ValidationError({"account": "Akkauntni o‘chirish so‘rovi allaqachon yuborilgan."})
        deletion = DeletionRequest.objects.create(
            user=locked_user, reason=reason, reason_other=reason_other.strip()
        )
        locked_user.is_blocked = True
        locked_user.auth_version += 1
        locked_user.save(update_fields=("is_blocked", "auth_version"))
        audit_event("account_deletion_requested", user=locked_user, entity_type="DeletionRequest", entity_id=deletion.pk)
    return deletion


def restore_account(*, phone: str, password: str) -> User:
    phone = normalize_uz_phone(phone)
    user = User.objects.filter(phone=phone, role=User.Role.SHOP_OWNER).first()
    if user is None or not user.check_password(password):
        raise AuthenticationFailed("Telefon raqami yoki parol noto‘g‘ri.")
    with transaction.atomic():
        deletion = (
            user.deletion_requests.select_for_update()
            .filter(status=DeletionRequest.Status.PENDING)
            .order_by("-requested_at")
            .first()
        )
        if deletion is None or deletion.scheduled_for <= timezone.now():
            raise ValidationError({"account": "Akkauntni tiklash muddati tugagan."})
        deletion.status = DeletionRequest.Status.CANCELLED
        deletion.processed_at = timezone.now()
        deletion.save(update_fields=("status", "processed_at"))
        user.is_blocked = False
        user.is_active = True
        user.auth_version += 1
        user.save(update_fields=("is_blocked", "is_active", "auth_version"))
    audit_event("account_deletion_cancelled", user=user, entity_type="DeletionRequest", entity_id=deletion.pk)
    return user
