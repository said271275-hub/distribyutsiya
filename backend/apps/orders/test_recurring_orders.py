from datetime import time, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.orders.models import (
    Order,
    OrderItem,
    RecurringOrderDraft,
    RecurringOrderSchedule,
    SmsOutbox,
)
from apps.orders.recurring_services import create_recurring_drafts
from apps.payments.models import ShopBalance


class RecurringOrderApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Sirdaryo", contact_phone="+998900000001"
        )
        cls.other_company = Company.objects.create(name="Boshqa kompaniya")
        cls.owner = User.objects.create_user(
            phone="+998900000010", password="test-pass", role=User.Role.SHOP_OWNER
        )
        cls.shop = Shop.objects.create(
            owner=cls.owner,
            name="Guliston market",
            phone_primary="+998900000011",
            address="Markaz",
            district="Guliston",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        cls.link = CompanyShopLink.objects.create(company=cls.company, shop=cls.shop)
        cls.product = Product.objects.create(
            company=cls.company,
            name="Suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
        )
        ShopPrice.objects.create(
            company=cls.company,
            shop=cls.shop,
            product=cls.product,
            price=Decimal("800.00"),
            discount_percent=Decimal("10.00"),
        )
        cls.other_owner = User.objects.create_user(
            phone="+998900000020", password="test-pass", role=User.Role.SHOP_OWNER
        )
        cls.other_shop = Shop.objects.create(
            owner=cls.other_owner,
            name="Boshqa do‘kon",
            phone_primary="+998900000021",
            address="Boshqa manzil",
            district="Yangiyer",
            latitude=Decimal("40.850000"),
            longitude=Decimal("68.670000"),
        )
        CompanyShopLink.objects.create(company=cls.other_company, shop=cls.other_shop)
        cls.other_product = Product.objects.create(
            company=cls.other_company,
            name="Yopiq mahsulot",
            unit=Product.Unit.PIECE,
            price=Decimal("9000.00"),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    @staticmethod
    def scheduled_weekday(days_ahead=2):
        return (timezone.localdate() + timedelta(days=days_ahead)).weekday()

    def schedule_payload(self, **overrides):
        data = {
            "company_id": self.company.pk,
            "name": "Haftalik suv",
            "weekdays": [self.scheduled_weekday()],
            "items": [{"product_id": self.product.pk, "quantity": "2.00"}],
        }
        data.update(overrides)
        return data

    def create_schedule(self, **overrides):
        response = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(**overrides),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def create_draft(self):
        self.create_schedule()
        call_command("create_recurring_orders")
        return RecurringOrderDraft.objects.get()

    def test_command_creates_one_draft_and_is_idempotent(self):
        schedule = self.create_schedule()

        first_count = create_recurring_drafts()
        second_count = create_recurring_drafts()

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(
            RecurringOrderDraft.objects.filter(schedule_id=schedule["id"]).count(), 1
        )
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(SmsOutbox.objects.filter(
            event=SmsOutbox.Event.RECURRING_DRAFT
        ).count(), 1)

    def test_draft_is_not_an_order_or_balance_entry(self):
        draft = self.create_draft()

        self.assertEqual(draft.status, RecurringOrderDraft.Status.PENDING)
        self.assertEqual(Order.objects.count(), 0)
        self.assertFalse(ShopBalance.objects.filter(shop=self.shop).exists())

    def test_archived_product_is_skipped_when_draft_is_created(self):
        self.create_schedule()
        self.product.is_archived = True
        self.product.save(update_fields=("is_archived", "updated_at"))

        call_command("create_recurring_orders")
        draft = RecurringOrderDraft.objects.get()

        self.assertEqual(draft.items.count(), 0)
        self.assertEqual(
            draft.skipped_products,
            [{"id": self.product.pk, "name": self.product.name}],
        )

    def test_confirm_uses_current_discounted_price_and_skips_archived_product(self):
        second_product = Product.objects.create(
            company=self.company,
            name="Sharbat",
            unit=Product.Unit.BOX,
            price=Decimal("500.00"),
        )
        draft = self.create_draft()
        schedule = draft.schedule
        schedule.items.create(
            company=self.company,
            product=second_product,
            quantity=Decimal("3.00"),
        )
        draft.items.create(
            company=self.company,
            product=second_product,
            quantity=Decimal("3.00"),
        )
        self.product.is_archived = True
        self.product.save(update_fields=("is_archived", "updated_at"))
        ShopPrice.objects.update_or_create(
            company=self.company,
            shop=self.shop,
            product=second_product,
            defaults={"price": Decimal("400.00"), "discount_percent": Decimal("25.00")},
        )

        response = self.client.post(
            f"/api/v1/shop/recurring-drafts/{draft.pk}/confirm/"
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], RecurringOrderDraft.Status.CONFIRMED)
        self.assertEqual(len(response.data["skipped_products"]), 1)
        order = Order.objects.get(pk=response.data["order_id"])
        self.assertEqual(order.total_price, Decimal("900.00"))
        self.assertEqual(
            list(order.items.values_list("unit_price", flat=True)),
            [Decimal("300.00")],
        )
        self.assertFalse(ShopBalance.objects.filter(shop=self.shop).exists())

    def test_other_shop_cannot_view_or_change_schedule_or_draft(self):
        schedule = self.create_schedule()
        call_command("create_recurring_orders")
        draft = RecurringOrderDraft.objects.get()
        self.client.force_authenticate(self.other_owner)

        listing = self.client.get("/api/v1/shop/recurring-orders/")
        patch_response = self.client.patch(
            f"/api/v1/shop/recurring-orders/{schedule['id']}/",
            {"name": "Buzilgan"},
            format="json",
        )
        confirm_response = self.client.post(
            f"/api/v1/shop/recurring-drafts/{draft.pk}/confirm/"
        )

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["schedules"], [])
        self.assertEqual(listing.data["drafts"], [])
        self.assertEqual(patch_response.status_code, 404)
        self.assertEqual(confirm_response.status_code, 404)

    def test_unlinked_company_cannot_be_used_for_schedule(self):
        self.link.is_active = False
        self.link.save(update_fields=("is_active", "updated_at"))

        response = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecurringOrderSchedule.objects.count(), 0)

    def test_schedule_cannot_use_another_company_catalog(self):
        response = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(
                company_id=self.other_company.pk,
                items=[{"product_id": self.other_product.pk, "quantity": "1.00"}],
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecurringOrderSchedule.objects.count(), 0)

    def test_schedule_and_item_limits_are_enforced(self):
        for index in range(10):
            self.create_schedule(name=f"Jadval {index}")

        too_many_schedules = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(name="Ortiqcha jadval"),
            format="json",
        )
        too_many_items = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(items=[
                {"product_id": self.product.pk, "quantity": "1.00"}
            ] * 51),
            format="json",
        )
        excessive_quantity = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(items=[
                {"product_id": self.product.pk, "quantity": "10000.01"}
            ]),
            format="json",
        )
        negative_quantity = self.client.post(
            "/api/v1/shop/recurring-orders/",
            self.schedule_payload(items=[
                {"product_id": self.product.pk, "quantity": "-1.00"}
            ]),
            format="json",
        )

        self.assertEqual(too_many_schedules.status_code, 400)
        self.assertEqual(too_many_items.status_code, 400)
        self.assertEqual(excessive_quantity.status_code, 400)
        self.assertEqual(negative_quantity.status_code, 400)
        self.assertEqual(RecurringOrderSchedule.objects.count(), 10)

    def test_schedule_can_be_edited_paused_resumed_and_archived(self):
        schedule = self.create_schedule()
        schedule_id = schedule["id"]

        edited = self.client.patch(
            f"/api/v1/shop/recurring-orders/{schedule_id}/",
            {"name": "Yangi jadval"},
            format="json",
        )
        paused = self.client.post(
            f"/api/v1/shop/recurring-orders/{schedule_id}/pause/"
        )
        resumed = self.client.post(
            f"/api/v1/shop/recurring-orders/{schedule_id}/resume/"
        )
        archived = self.client.post(
            f"/api/v1/shop/recurring-orders/{schedule_id}/archive/"
        )
        resume_archived = self.client.post(
            f"/api/v1/shop/recurring-orders/{schedule_id}/resume/"
        )

        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data["name"], "Yangi jadval")
        self.assertFalse(paused.data["is_active"])
        self.assertTrue(resumed.data["is_active"])
        self.assertTrue(archived.data["is_archived"])
        self.assertEqual(resume_archived.status_code, 400)

    def test_existing_cutoff_still_blocks_draft_confirmation(self):
        self.create_schedule(weekdays=[
            (timezone.localdate() + timedelta(days=1)).weekday()
        ])
        call_command("create_recurring_orders")
        draft = RecurringOrderDraft.objects.get()
        self.company.order_cutoff_time = time(0, 0)
        self.company.save(update_fields=("order_cutoff_time", "updated_at"))

        response = self.client.post(
            f"/api/v1/shop/recurring-drafts/{draft.pk}/confirm/"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        draft.refresh_from_db()
        self.assertEqual(draft.status, RecurringOrderDraft.Status.PENDING)

    def test_expired_pending_draft_cannot_become_order(self):
        schedule = self.create_schedule(
            weekdays=[(timezone.localdate() + timedelta(days=1)).weekday()]
        )
        call_command("create_recurring_orders")
        draft = RecurringOrderDraft.objects.get(schedule_id=schedule["id"])
        delivery_date = draft.delivery_date

        create_recurring_drafts(today=delivery_date)
        draft.refresh_from_db()
        response = self.client.post(
            f"/api/v1/shop/recurring-drafts/{draft.pk}/confirm/"
        )

        self.assertEqual(draft.status, RecurringOrderDraft.Status.EXPIRED)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_recurring_draft_sms_is_suppressed_when_shop_notifications_are_off(self):
        draft = self.create_draft()
        notification = SmsOutbox.objects.get(
            recurring_draft=draft, event=SmsOutbox.Event.RECURRING_DRAFT
        )
        self.shop.sms_notifications_enabled = False
        self.shop.save(update_fields=("sms_notifications_enabled", "updated_at"))

        with patch("apps.orders.sms_notifications.get_otp_provider") as get_provider:
            from apps.orders.sms_notifications import deliver_sms_notification

            deliver_sms_notification(notification.pk)

        notification.refresh_from_db()
        self.assertEqual(notification.state, SmsOutbox.State.SUPPRESSED)
        get_provider.assert_not_called()

    def test_recurring_draft_sms_has_only_draft_status_and_identifier(self):
        draft = self.create_draft()
        notification = SmsOutbox.objects.get(
            recurring_draft=draft, event=SmsOutbox.Event.RECURRING_DRAFT
        )
        provider = Mock()
        with patch(
            "apps.orders.sms_notifications.get_otp_provider",
            return_value=provider,
        ):
            from apps.orders.sms_notifications import deliver_sms_notification

            deliver_sms_notification(notification.pk)

        provider.send.assert_called_once()
        message = provider.send.call_args.args[1]
        self.assertIn(f"#{draft.pk}", message)
        self.assertIn("tasdiqlashni kutmoqda", message)
        self.assertNotIn("900", message)
