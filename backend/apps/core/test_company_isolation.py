from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import DeletionRequest, User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.logistics.models import DriverProfile, Trip, TripStop, TripStopOrder, Vehicle
from apps.orders.models import Order, OrderItem
from apps.payments.models import BalanceEntry, ShopBalance


class CompanyIsolationModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company_a = Company.objects.create(name="Kompaniya A")
        cls.company_b = Company.objects.create(name="Kompaniya B")

        owner = User.objects.create_user(
            phone="+998900000001", role=User.Role.SHOP_OWNER
        )
        cls.shop = Shop.objects.create(
            owner=owner,
            name="Sinov do‘koni",
            phone_primary="+998900000002",
            address="Guliston",
            district="Guliston",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        CompanyShopLink.objects.create(company=cls.company_a, shop=cls.shop)
        cls.product_a = Product.objects.create(
            company=cls.company_a, name="A mahsulot", unit=Product.Unit.PIECE,
            price=Decimal("1000.00"),
        )
        cls.product_b = Product.objects.create(
            company=cls.company_b, name="B mahsulot", unit=Product.Unit.PIECE,
            price=Decimal("1500.00"),
        )
        cls.order = Order.objects.create(
            company=cls.company_a,
            shop=cls.shop,
            delivery_date="2026-10-15",
        )
        driver_user = User.objects.create_user(
            phone="+998900000003",
            company=cls.company_a,
            role=User.Role.DRIVER,
        )
        cls.driver = DriverProfile.objects.create(
            company=cls.company_a, user=driver_user
        )
        cls.vehicle = Vehicle.objects.create(
            company=cls.company_a,
            name="A mashina",
            plate_number="01A001AA",
            capacity=Decimal("1000.00"),
        )
        cls.trip = Trip.objects.create(
            company=cls.company_a,
            date="2026-10-15",
            vehicle=cls.vehicle,
            driver=cls.driver,
        )
        cls.stop = TripStop.objects.create(
            company=cls.company_a, trip=cls.trip, shop=cls.shop, sequence=1
        )

    def test_shop_price_rejects_product_from_another_company(self):
        price = ShopPrice(
            company=self.company_a,
            shop=self.shop,
            product=self.product_b,
            discount_percent=Decimal("5.00"),
        )
        with self.assertRaises(ValidationError):
            price.full_clean()

    def test_order_item_rejects_product_from_another_company(self):
        item = OrderItem(
            company=self.company_a,
            order=self.order,
            product=self.product_b,
            quantity=Decimal("2.00"),
            unit_price=Decimal("1500.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_trip_stop_order_rejects_order_from_another_company(self):
        other_shop_owner = User.objects.create_user(
            phone="+998900000004", role=User.Role.SHOP_OWNER
        )
        other_shop = Shop.objects.create(
            owner=other_shop_owner,
            name="B do‘kon",
            phone_primary="+998900000005",
            address="Yangiyer",
            district="Yangiyer",
            latitude=Decimal("40.850000"),
            longitude=Decimal("68.670000"),
        )
        CompanyShopLink.objects.create(company=self.company_b, shop=other_shop)
        other_order = Order.objects.create(
            company=self.company_b,
            shop=other_shop,
            delivery_date="2026-10-15",
        )
        link = TripStopOrder(
            company=self.company_a, trip_stop=self.stop, order=other_order
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_phone_login_identifier_is_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    phone="+998900000001", role=User.Role.SHOP_OWNER
                )

    def test_balance_entry_updates_cached_balance_only_once(self):
        entry = BalanceEntry.objects.create(
            company=self.company_a,
            shop=self.shop,
            amount=Decimal("2000.00"),
            direction=BalanceEntry.Direction.DEBIT,
            order=self.order,
        )

        entry.post()
        entry.post()

        balance = ShopBalance.objects.get(company=self.company_a, shop=self.shop)
        self.assertEqual(balance.current_balance, Decimal("2000.00"))
        self.assertIsNotNone(entry.posted_at)

    def test_deletion_request_is_scheduled_thirty_days_after_request(self):
        request = DeletionRequest.objects.create(
            user=self.shop.owner, reason="Test sabab"
        )

        self.assertEqual(
            request.scheduled_for, request.requested_at + timedelta(days=30)
        )
