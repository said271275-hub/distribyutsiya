from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.models import DeletionRequest, User
from apps.audit.models import AuditLog
from apps.catalog.models import ContainerMovement, Product, ReturnableContainer
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.core.management.commands.reset_dev_users import Command
from apps.logistics.models import DriverProfile, Trip, TripStop, TripStopOrder, Vehicle
from apps.orders.models import Order, OrderItem
from apps.payments.models import BalanceEntry, Payment, ShopBalance


@override_settings(DEBUG=True, DEV_OTP_ENABLED=True)
class ResetDevUsersCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", "--with-demo-users", stdout=StringIO())
        cls.company = Company.objects.get(name="Sirdaryo Distribyutsiya")
        cls.user = User.objects.get(phone="+998900030001")
        cls.shop = Shop.objects.get(phone_primary="+998900020001")
        cls.product = Product.objects.filter(company=cls.company).first()
        cls.vehicle = Vehicle.objects.filter(company=cls.company).first()
        cls.driver = DriverProfile.objects.get(user=cls.user)
        cls.container = ReturnableContainer.objects.create(
            company=cls.company, name="Sinov tara", deposit_amount=Decimal("500.00")
        )

        cls.order = Order.objects.create(
            company=cls.company,
            shop=cls.shop,
            status=Order.Status.CONFIRMED,
            delivery_date=timezone.localdate() + timedelta(days=1),
        )
        OrderItem.objects.create(
            company=cls.company,
            order=cls.order,
            product=cls.product,
            quantity=Decimal("2.00"),
            unit_price=Decimal("100.00"),
        )
        cls.order.recalculate_total()

        cls.balance = ShopBalance.objects.create(
            company=cls.company, shop=cls.shop, current_balance=Decimal("200.00")
        )
        cls.payment = Payment.objects.create(
            company=cls.company,
            shop=cls.shop,
            amount=Decimal("50.00"),
            method=Payment.Method.CASH,
            status=Payment.Status.CONFIRMED,
        )
        cls.entry = BalanceEntry.objects.create(
            company=cls.company,
            shop=cls.shop,
            amount=Decimal("50.00"),
            direction=BalanceEntry.Direction.DEBIT,
            payment=cls.payment,
        )
        cls.entry.post()
        cls.movement = ContainerMovement.objects.create(
            company=cls.company,
            shop=cls.shop,
            container=cls.container,
            quantity_delta=Decimal("1.00"),
            order=cls.order,
        )

        cls.trip = Trip.objects.create(
            company=cls.company,
            date=timezone.localdate() + timedelta(days=1),
            vehicle=cls.vehicle,
            driver=cls.driver,
        )
        cls.stop = TripStop.objects.create(
            company=cls.company, trip=cls.trip, shop=cls.shop, sequence=1
        )
        cls.trip_order = TripStopOrder.objects.create(
            company=cls.company, trip_stop=cls.stop, order=cls.order
        )
        cls.deletion = DeletionRequest.objects.create(
            user=cls.user, reason=DeletionRequest.Reason.OTHER
        )
        cls.audit = AuditLog.objects.create(
            company=cls.company,
            actor=cls.user,
            action="reset-test",
            entity_type="User",
            entity_id=str(cls.user.pk),
        )
        cls.refresh_token = RefreshToken.for_user(cls.user)

    def execute_dry_run(self, output):
        call_command("reset_dev_users", stdout=output)

    def test_dry_run_reports_counts_without_deleting_anything(self):
        self.assertTrue(OutstandingToken.objects.filter(user=self.user).exists())
        before = Command()._counts()
        output = StringIO()

        self.execute_dry_run(output)

        self.assertEqual(Command()._counts(), before)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
        self.assertIn("Quruq sinov", output.getvalue())
        self.assertIn("foydalanuvchi: 23", output.getvalue())
        self.assertIn("Qoladi: 1 kompaniya", output.getvalue())

    def test_refuses_to_run_unless_both_local_safety_flags_are_enabled(self):
        for debug, dev_otp in ((False, True), (True, False)):
            with self.subTest(debug=debug, dev_otp=dev_otp):
                with override_settings(DEBUG=debug, DEV_OTP_ENABLED=dev_otp):
                    with self.assertRaises(CommandError):
                        self.execute_dry_run(StringIO())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_confirmation_does_not_delete_anything(self):
        with patch("builtins.input", return_value="NO"):
            with self.assertRaises(CommandError):
                call_command(
                    "reset_dev_users",
                    "--yes-delete-everything",
                    stdout=StringIO(),
                )
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_confirmed_reset_deletes_user_data_and_preserves_company_catalog(self):
        with patch("builtins.input", return_value="DELETE"):
            call_command(
                "reset_dev_users",
                "--yes-delete-everything",
                stdout=StringIO(),
            )

        self.assertFalse(User.objects.exists())
        self.assertFalse(Shop.objects.exists())
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Trip.objects.exists())
        self.assertFalse(TripStop.objects.exists())
        self.assertFalse(TripStopOrder.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(BalanceEntry.objects.exists())
        self.assertFalse(ShopBalance.objects.exists())
        self.assertFalse(ContainerMovement.objects.exists())
        self.assertFalse(DeletionRequest.objects.exists())
        self.assertFalse(AuditLog.objects.exists())
        self.assertFalse(OutstandingToken.objects.exists())
        self.assertTrue(Company.objects.filter(pk=self.company.pk).exists())
        self.assertTrue(Product.objects.filter(company=self.company).exists())
        self.assertEqual(Vehicle.objects.filter(company=self.company).count(), 2)
        self.assertTrue(ReturnableContainer.objects.filter(pk=self.container.pk).exists())
