from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.sms import SmsProviderError
from apps.audit.models import AuditLog
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.core.admin_api import transition_order
from apps.orders.models import Order, OrderItem, SmsOutbox
from apps.orders.shop_services import create_shop_order
from apps.orders.sms_notifications import (
    _message,
    deliver_sms_notification,
    queue_order_sms,
)


class OrderSmsNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Kompaniya A")
        cls.product = Product.objects.create(
            company=cls.company,
            name="Mahsulot",
            unit=Product.Unit.PIECE,
            price=Decimal("0.00"),
        )
        cls.owner = User.objects.create_user(
            phone="+998900000010",
            password="Temporary-password-1!",
            role=User.Role.SHOP_OWNER,
        )
        cls.shop = Shop.objects.create(
            owner=cls.owner,
            name="A do‘kon",
            owner_name="A egasi",
            phone_primary="+998900000011",
            address="Maxfiy manzil",
            district="Tuman",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        CompanyShopLink.objects.create(company=cls.company, shop=cls.shop)
        cls.order = Order.objects.create(
            company=cls.company,
            shop=cls.shop,
            delivery_date=timezone.localdate() + timedelta(days=1),
            total_price=Decimal("12345.00"),
        )

    def test_order_sms_is_submitted_only_after_commit(self):
        with patch("apps.orders.sms_notifications.submit_sms_notification") as submit:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                notification = queue_order_sms(
                    self.order,
                    SmsOutbox.Event.RECEIVED,
                )
                submit.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            submit.assert_called_once_with(notification.pk)

    def test_failed_sms_does_not_break_order_transition_and_is_audited_safely(self):
        provider = Mock()
        provider.send.side_effect = [SmsProviderError("network_error"), None]
        with patch(
            "apps.orders.sms_notifications.get_otp_provider",
            return_value=provider,
        ), patch(
            "apps.orders.sms_notifications.submit_sms_notification",
            side_effect=deliver_sms_notification,
        ):
            with self.assertLogs(
                "apps.orders.sms_notifications",
                level="WARNING",
            ) as captured:
                with self.captureOnCommitCallbacks(execute=True):
                    result = transition_order(
                        order=self.order,
                        actor=None,
                        target=Order.Status.CONFIRMED,
                        reason="Buyurtma tasdiqlandi",
                    )

        self.assertEqual(result.status, Order.Status.CONFIRMED)
        notification = SmsOutbox.objects.get(
            order=self.order,
            event=SmsOutbox.Event.CONFIRMED,
        )
        self.assertEqual(notification.state, SmsOutbox.State.SENT)
        self.assertEqual(notification.attempts, 2)
        provider.send.assert_called()
        log_text = "\n".join(captured.output)
        self.assertIn("0010", log_text)
        self.assertNotIn(self.owner.phone, log_text)
        audit = AuditLog.objects.get(
            action="sms.delivery_failed",
            entity_id=str(notification.pk),
        )
        self.assertEqual(audit.after["phone_last4"], "0010")
        self.assertEqual(audit.after["error_code"], "network_error")
        self.assertNotIn(self.owner.phone, str(audit.after))

    def test_failed_sms_does_not_break_order_creation_or_delivery(self):
        provider = Mock()
        provider.send.side_effect = [
            SmsProviderError("network_error"),
            None,
            SmsProviderError("network_error"),
            None,
        ]
        with patch(
            "apps.orders.sms_notifications.get_otp_provider",
            return_value=provider,
        ), patch(
            "apps.orders.sms_notifications.submit_sms_notification",
            side_effect=deliver_sms_notification,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                order = create_shop_order(
                    user=self.owner,
                    data={
                        "company_id": self.company.pk,
                        "delivery_date": timezone.localdate() + timedelta(days=1),
                        "items": [{"product_id": self.product.pk, "quantity": Decimal("1.00")}],
                    },
                )
                order.status = Order.Status.IN_TRANSIT
                order.save(update_fields=("status", "updated_at"))
                item = order.items.get()
                delivered = transition_order(
                    order=order,
                    actor=None,
                    target=Order.Status.DELIVERED,
                    reason="Yetkazildi",
                    delivered_items=[{"item_id": item.pk, "quantity": item.quantity}],
                )

        self.assertEqual(delivered.status, Order.Status.DELIVERED)
        self.assertTrue(
            SmsOutbox.objects.filter(order=order, event=SmsOutbox.Event.RECEIVED).exists()
        )
        self.assertTrue(
            SmsOutbox.objects.filter(order=order, event=SmsOutbox.Event.DELIVERED).exists()
        )

    def test_disabled_order_notices_are_suppressed(self):
        self.shop.sms_notifications_enabled = False
        self.shop.save(update_fields=("sms_notifications_enabled",))
        notification = SmsOutbox.objects.create(
            order=self.order,
            event=SmsOutbox.Event.RECEIVED,
        )
        with patch("apps.orders.sms_notifications.get_otp_provider") as provider:
            deliver_sms_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.state, SmsOutbox.State.SUPPRESSED)
        provider.assert_not_called()

    def test_disabled_order_notices_do_not_disable_login_otp(self):
        from rest_framework.test import APIClient

        self.shop.sms_notifications_enabled = False
        self.shop.save(update_fields=("sms_notifications_enabled",))
        provider = Mock()
        provider.generate_code.return_value = "472901"
        with patch(
            "apps.accounts.sms.get_otp_provider",
            return_value=provider,
        ):
            response = APIClient().post(
                "/api/auth/login/otp/",
                {"phone": self.owner.phone, "password": "Temporary-password-1!"},
                format="json",
            )

        self.assertEqual(response.status_code, 202, response.data)
        provider.send.assert_called_once()

    def test_mismatched_company_and_shop_never_sends_sms(self):
        other_company = Company.objects.create(name="Kompaniya B")
        mismatched_order = Order.objects.create(
            company=other_company,
            shop=self.shop,
            delivery_date=timezone.localdate() + timedelta(days=1),
        )
        notification = SmsOutbox.objects.create(
            order=mismatched_order,
            event=SmsOutbox.Event.RECEIVED,
        )
        with patch("apps.orders.sms_notifications.get_otp_provider") as provider:
            deliver_sms_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.state, SmsOutbox.State.FAILED)
        provider.assert_not_called()

    def test_store_owner_can_change_only_own_sms_preference(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.patch(
            "/api/v1/shop/profile/",
            {"sms_notifications_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.sms_notifications_enabled)

        other_owner = User.objects.create_user(
            phone="+998900000012",
            password="Another-password-2!",
            role=User.Role.SHOP_OWNER,
        )
        client.force_authenticate(other_owner)
        denied = client.patch(
            "/api/v1/shop/profile/",
            {"sms_notifications_enabled": True},
            format="json",
        )
        self.assertEqual(denied.status_code, 404)
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.sms_notifications_enabled)

    def test_order_sms_has_no_name_amount_or_address(self):
        notification = SmsOutbox(
            order=self.order,
            event=SmsOutbox.Event.TRIP_ASSIGNED,
            eta=timezone.now(),
        )
        message = _message(notification)

        self.assertIn(f"#{self.order.pk}", message)
        self.assertIn("Yetib borish vaqti", message)
        self.assertNotIn(self.owner.phone, message)
        self.assertNotIn(self.shop.owner_name, message)
        self.assertNotIn(self.shop.address, message)
        self.assertNotIn("12345", message)
