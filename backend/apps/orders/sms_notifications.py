import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import timedelta
from functools import partial

from django.db import close_old_connections, models, transaction
from django.utils import timezone

from apps.accounts.sms import SmsProviderError, get_otp_provider
from apps.audit.models import AuditLog
from apps.companies.models import CompanyShopLink
from apps.orders.models import SmsOutbox

logger = logging.getLogger(__name__)
_SMS_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="order-sms")
_MAX_ATTEMPTS = 3
_LEASE = timedelta(minutes=2)


def _phone_suffix(phone: str) -> str:
    return "".join(character for character in phone if character.isdigit())[-4:]


def _message(notification: SmsOutbox) -> str:
    if notification.event == SmsOutbox.Event.RECURRING_DRAFT:
        return (
            f"Takroriy buyurtma #{notification.recurring_draft_id} "
            "tasdiqlashni kutmoqda."
        )
    order_id = notification.order_id
    messages = {
        SmsOutbox.Event.RECEIVED: f"Buyurtma #{order_id} qabul qilindi.",
        SmsOutbox.Event.CONFIRMED: f"Buyurtma #{order_id} tasdiqlandi.",
        SmsOutbox.Event.TRIP_ASSIGNED: (
            f"Buyurtma #{order_id} reysga qo‘shildi. Yetib borish vaqti: "
            f"{timezone.localtime(notification.eta).strftime('%d.%m %H:%M')}."
            if notification.eta
            else f"Buyurtma #{order_id} reysga qo‘shildi. Yetib borish vaqti aniqlanmagan."
        ),
        SmsOutbox.Event.DELIVERED: f"Buyurtma #{order_id} yetkazildi.",
        SmsOutbox.Event.SHOP_CLOSED: (
            f"Buyurtma #{order_id}: muammo yuz berdi, do‘kon yopiq."
        ),
        SmsOutbox.Event.PARTIAL_DELIVERY: (
            f"Buyurtma #{order_id}: qisman yetkazildi."
        ),
    }
    return messages[notification.event]


def queue_order_sms(order, event: str, *, eta=None) -> SmsOutbox:
    notification = SmsOutbox.objects.create(order=order, event=event, eta=eta)
    transaction.on_commit(partial(submit_sms_notification, notification.pk))
    return notification


def queue_recurring_draft_sms(draft) -> SmsOutbox:
    notification = SmsOutbox.objects.create(
        recurring_draft=draft,
        event=SmsOutbox.Event.RECURRING_DRAFT,
    )
    transaction.on_commit(partial(submit_sms_notification, notification.pk))
    return notification


def _record_failure(notification_id: int, error_code: str, phone: str) -> float | None:
    now = timezone.now()
    retry_delay = None
    with transaction.atomic():
        notification = SmsOutbox.objects.select_for_update().get(pk=notification_id)
        if notification.attempts >= _MAX_ATTEMPTS:
            notification.state = SmsOutbox.State.FAILED
        else:
            notification.state = SmsOutbox.State.PENDING
            retry_delay = 0.5 * notification.attempts
            notification.next_attempt_at = now + timedelta(seconds=retry_delay)
        notification.last_error_code = error_code[:64]
        notification.claimed_at = None
        notification.save(
            update_fields=(
                "state",
                "next_attempt_at",
                "last_error_code",
                "claimed_at",
            )
        )
        company_id = (
            notification.order.company_id
            if notification.order_id
            else notification.recurring_draft.company_id
        )
        AuditLog.objects.create(
            company_id=company_id,
            action="sms.delivery_failed",
            entity_type="SmsOutbox",
            entity_id=str(notification.pk),
            after={
                "event": notification.event,
                "attempt": notification.attempts,
                "error_code": error_code[:64],
                "phone_last4": _phone_suffix(phone),
            },
        )
    return retry_delay


def deliver_sms_notification(notification_id: int) -> None:
    worker_thread = threading.current_thread() is not threading.main_thread()
    if worker_thread:
        close_old_connections()
    try:
        now = timezone.now()
        with transaction.atomic():
            notification = (
                SmsOutbox.objects.select_for_update()
                .select_related(
                    "order__company",
                    "order__shop__owner",
                    "recurring_draft__company",
                    "recurring_draft__schedule__shop__owner",
                )
                .filter(pk=notification_id)
                .first()
            )
            if notification is None or notification.state in (
                SmsOutbox.State.SENT,
                SmsOutbox.State.FAILED,
                SmsOutbox.State.SUPPRESSED,
            ):
                return
            if notification.state == SmsOutbox.State.PENDING and notification.next_attempt_at > now:
                return
            if (
                notification.state == SmsOutbox.State.SENDING
                and notification.claimed_at
                and notification.claimed_at > now - _LEASE
            ):
                return

            if notification.order_id:
                company_id = notification.order.company_id
                shop = notification.order.shop
            else:
                company_id = notification.recurring_draft.company_id
                shop = notification.recurring_draft.schedule.shop
            if not shop.sms_notifications_enabled:
                notification.state = SmsOutbox.State.SUPPRESSED
                notification.claimed_at = None
                notification.save(update_fields=("state", "claimed_at"))
                return
            if not CompanyShopLink.objects.filter(
                company_id=company_id,
                shop_id=shop.pk,
                is_active=True,
                company__is_active=True,
            ).exists():
                notification.state = SmsOutbox.State.FAILED
                notification.last_error_code = "tenant_link_inactive"
                notification.save(update_fields=("state", "last_error_code"))
                return

            phone = shop.owner.phone
            notification.state = SmsOutbox.State.SENDING
            notification.attempts += 1
            notification.claimed_at = now
            notification.next_attempt_at = now + _LEASE
            notification.save(
                update_fields=("state", "attempts", "claimed_at", "next_attempt_at")
            )
            message = _message(notification)

        get_otp_provider().send(phone, message)
        with transaction.atomic():
            notification = SmsOutbox.objects.select_for_update().get(pk=notification_id)
            notification.state = SmsOutbox.State.SENT
            notification.sent_at = timezone.now()
            notification.claimed_at = None
            notification.last_error_code = ""
            notification.save(
                update_fields=("state", "sent_at", "claimed_at", "last_error_code")
            )
    except SmsProviderError as error:
        order_data = (
            SmsOutbox.objects.filter(pk=notification_id)
            .values(
                "order__shop__owner__phone",
                "recurring_draft__schedule__shop__owner__phone",
            )
            .first()
        )
        phone = ""
        if order_data:
            phone = (
                order_data["order__shop__owner__phone"]
                or order_data["recurring_draft__schedule__shop__owner__phone"]
                or ""
            )
        retry_delay = _record_failure(notification_id, error.code, phone)
        logger.warning(
            "Buyurtma SMS yuborilmadi: xabar=%s raqam_oxiri=%s xato=%s",
            notification_id,
            _phone_suffix(phone),
            error.code,
        )
        if retry_delay is not None:
            time.sleep(retry_delay)
            deliver_sms_notification(notification_id)
    finally:
        if worker_thread:
            close_old_connections()


def _log_unexpected_failure(future: Future) -> None:
    error = future.exception()
    if error is not None:
        logger.error("SMS navbatidagi vazifa bajarilmadi: xato_turi=%s", type(error).__name__)


def submit_sms_notification(notification_id: int) -> None:
    try:
        future = _SMS_EXECUTOR.submit(deliver_sms_notification, notification_id)
    except RuntimeError as error:
        logger.error(
            "SMS navbatiga vazifa qo‘shilmadi: xabar=%s xato_turi=%s",
            notification_id,
            type(error).__name__,
        )
        return
    future.add_done_callback(_log_unexpected_failure)


def process_pending_sms(limit: int = 50) -> int:
    now = timezone.now()
    stale_before = now - _LEASE
    notification_ids = list(
        SmsOutbox.objects.filter(
            models.Q(
                state=SmsOutbox.State.PENDING,
                next_attempt_at__lte=now,
            )
            | models.Q(
                state=SmsOutbox.State.SENDING,
                claimed_at__lte=stale_before,
            )
        )
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )
    for notification_id in notification_ids:
        deliver_sms_notification(notification_id)
    return len(notification_ids)
