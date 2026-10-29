import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.utils import timezone
from django.db.models import Sum
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.core.admin_api import transition_order
from apps.logistics.models import DriverProfile, Trip, TripStop, TripStopOrder, Vehicle
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.orders.shop_services import create_shop_order
from apps.payments.models import BalanceEntry, Payment, ShopBalance


class AdminReportsApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Kompaniya A")
        cls.other_company = Company.objects.create(name="Kompaniya B")
        cls.admin = User.objects.create_user(
            phone="+998900004101",
            password="Admin-password-123!",
            role=User.Role.COMPANY_ADMIN,
            company=cls.company,
        )
        cls.other_admin = User.objects.create_user(
            phone="+998900004102",
            password="Other-password-123!",
            role=User.Role.COMPANY_ADMIN,
            company=cls.other_company,
        )
        cls.owner = User.objects.create_user(
            phone="+998900004103",
            password="Owner-password-123!",
            role=User.Role.SHOP_OWNER,
        )
        cls.shop = Shop.objects.create(
            owner=cls.owner,
            name="A do‘kon",
            phone_primary="+998900004104",
            address="Guliston",
            district="Guliston",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        CompanyShopLink.objects.create(company=cls.company, shop=cls.shop)
        cls.other_owner = User.objects.create_user(
            phone="+998900004105",
            password="Owner-password-123!",
            role=User.Role.SHOP_OWNER,
        )
        cls.other_shop = Shop.objects.create(
            owner=cls.other_owner,
            name="B do‘kon",
            phone_primary="+998900004106",
            address="Yangiyer",
            district="Yangiyer",
            latitude=Decimal("40.850000"),
            longitude=Decimal("68.670000"),
        )
        CompanyShopLink.objects.create(company=cls.other_company, shop=cls.other_shop)
        cls.product = Product.objects.create(
            company=cls.company,
            name="Suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
        )
        cls.driver_user = User.objects.create_user(
            phone="+998900004107",
            password="Driver-password-123!",
            role=User.Role.DRIVER,
            company=cls.company,
        )
        cls.driver = DriverProfile.objects.create(
            company=cls.company,
            user=cls.driver_user,
        )
        cls.vehicle = Vehicle.objects.create(
            company=cls.company,
            name="A mashina",
            plate_number="01A101AA",
            capacity=Decimal("100.00"),
        )

    def setUp(self):
        self.client.force_authenticate(self.admin)
        self.today = timezone.localdate()
        self.yesterday = self.today - timedelta(days=1)

    def _order(self, *, status=Order.Status.DELIVERED, shop=None, quantity="3.00"):
        order = Order.objects.create(
            company=self.company,
            shop=shop or self.shop,
            status=status,
            delivery_date=self.today,
        )
        item = OrderItem.objects.create(
            company=self.company,
            order=order,
            product=self.product,
            quantity=Decimal(quantity),
            delivered_quantity=Decimal("2.00") if status == Order.Status.DELIVERED else None,
            unit_price=Decimal("1500.00"),
        )
        if status == Order.Status.DELIVERED:
            OrderItem.objects.create(
                company=self.company,
                order=order,
                product=self.product,
                quantity=Decimal("4.00"),
                delivered_quantity=Decimal("0.00"),
                unit_price=Decimal("2500.00"),
            )
        order.recalculate_total()
        return order, item

    def _history(self, order, status, day):
        history = OrderStatusHistory.objects.create(order=order, status=status)
        timestamp = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        OrderStatusHistory.objects.filter(pk=history.pk).update(created_at=timestamp)
        return history

    def _url(self, report, *, start=None, end=None, **params):
        return f"/api/v1/admin/reports/?report={report}&start_date={(start or self.yesterday).isoformat()}&end_date={(end or self.today).isoformat()}" + "".join(
            f"&{key}={value}" for key, value in params.items()
        )

    def test_sales_report_uses_delivered_quantity_and_groups_by_day(self):
        order, _item = self._order()
        self._history(order, Order.Status.DELIVERED, self.yesterday)
        cancelled, _item = self._order(status=Order.Status.CANCELLED)
        self._history(cancelled, Order.Status.CANCELLED, self.today)
        issue = AuditLog.objects.create(
            company=self.company,
            action="trip.stop.issue",
            entity_type="TripStop",
            entity_id="1",
            after={"reason": "shop_closed", "order_ids": [order.pk]},
        )
        AuditLog.objects.filter(pk=issue.pk).update(
            created_at=timezone.make_aware(datetime.combine(self.today, datetime.min.time()))
        )

        response = self.client.get(self._url("sales"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"], {
            "delivered_orders": 1,
            "delivered_amount": "3000.00",
            "cancelled_orders": 1,
            "problem_orders": 1,
        })
        self.assertEqual(response.data["rows"][0]["delivered_amount"], "3000.00")
        self.assertEqual(response.data["rows"][1]["cancelled_orders"], 1)
        self.assertEqual(response.data["rows"][1]["problem_orders"], 1)

    def test_product_csv_uses_uzbek_name_and_unit(self):
        order, _item = self._order()
        self._history(order, Order.Status.DELIVERED, self.today)

        response = self.client.get(self._url("products", export="csv"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("hisobot_mahsulotlar_", response["Content-Disposition"])
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(
            rows[0],
            ["Mahsulot", "Birlik", "Yetkazilgan miqdor", "Yetkazilgan summa"],
        )
        self.assertEqual(rows[1][1], "quti")

    def test_debtors_are_sorted_and_prepaid_shops_are_separate(self):
        ShopBalance.objects.create(
            company=self.company,
            shop=self.shop,
            current_balance=Decimal("4000.00"),
        )
        prepaid = Shop.objects.create(
            owner=User.objects.create_user(
                phone="+998900004108",
                password="Owner-password-123!",
                role=User.Role.SHOP_OWNER,
            ),
            name="Oldindan to‘lagan do‘kon",
            phone_primary="+998900004109",
            address="Guliston",
            district="Guliston",
            latitude=Decimal("40.841000"),
            longitude=Decimal("68.661000"),
        )
        CompanyShopLink.objects.create(company=self.company, shop=prepaid)
        ShopBalance.objects.create(
            company=self.company,
            shop=prepaid,
            current_balance=Decimal("-250.00"),
        )
        payment = Payment.objects.create(
            company=self.company,
            shop=self.shop,
            amount=Decimal("500.00"),
            method=Payment.Method.CASH,
            status=Payment.Status.CONFIRMED,
            paid_at=timezone.now() - timedelta(days=2),
        )
        entry = BalanceEntry.objects.create(
            company=self.company,
            shop=self.shop,
            amount=payment.amount,
            direction=BalanceEntry.Direction.CREDIT,
            payment=payment,
        )
        entry.post()

        response = self.client.get(self._url("debtors"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["debtors"][0]["shop_name"], self.shop.name)
        self.assertEqual(response.data["prepaid"][0]["shop_name"], prepaid.name)
        self.assertEqual(
            response.data["debtors"][0]["last_payment_date"],
            timezone.localtime(payment.paid_at).date().isoformat(),
        )

    def test_driver_and_product_reports_are_company_scoped(self):
        order, _item = self._order()
        trip = Trip.objects.create(
            company=self.company,
            date=self.today,
            vehicle=self.vehicle,
            driver=self.driver,
            status=Trip.Status.COMPLETED,
        )
        stop = TripStop.objects.create(
            company=self.company,
            trip=trip,
            shop=self.shop,
            sequence=1,
            delivered_at=timezone.now(),
        )
        TripStopOrder.objects.create(
            company=self.company,
            trip_stop=stop,
            order=order,
        )
        self._history(order, Order.Status.DELIVERED, self.today)
        AuditLog.objects.create(
            company=self.company,
            action="trip.stop.issue",
            entity_type="TripStop",
            entity_id=str(stop.pk),
            after={"reason": "shop_closed", "order_ids": [order.pk]},
        )
        foreign_order = Order.objects.create(
            company=self.other_company,
            shop=self.other_shop,
            status=Order.Status.DELIVERED,
            delivery_date=self.today,
        )
        OrderItem.objects.create(
            company=self.other_company,
            order=foreign_order,
            product=Product.objects.create(
                company=self.other_company,
                name="B mahsulot",
                unit=Product.Unit.BOX,
                price=Decimal("100.00"),
            ),
            quantity=Decimal("99.00"),
            delivered_quantity=Decimal("99.00"),
            unit_price=Decimal("100.00"),
        )
        self._history(foreign_order, Order.Status.DELIVERED, self.today)

        drivers = self.client.get(self._url("drivers"))
        products = self.client.get(self._url("products"))

        self.assertEqual(drivers.status_code, 200, drivers.data)
        self.assertEqual(len(drivers.data["rows"]), 1)
        self.assertEqual(drivers.data["rows"][0]["delivered_shops"], 1)
        self.assertEqual(drivers.data["rows"][0]["problem_shops"], 1)
        self.assertEqual(drivers.data["rows"][0]["reasons"]["shop_closed"]["count"], 1)
        self.assertEqual(products.status_code, 200, products.data)
        self.assertEqual(
            products.data["rows"],
            [{
                "product_id": self.product.pk,
                "product_name": self.product.name,
                "unit": self.product.unit,
                "delivered_quantity": "2.00",
                "delivered_amount": "3000.00",
            }],
        )

    def test_reports_reject_invalid_ranges_and_support_excel_csv(self):
        invalid = self.client.get(self._url("sales", start=self.today, end=self.yesterday))
        csv_response = self.client.get(self._url("sales", export="csv"))

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response["Content-Type"].startswith("text/csv"))
        self.assertTrue(csv_response.content.startswith(b"\xef\xbb\xbf"))

    def test_reports_reject_ranges_longer_than_366_days_and_limit_daily_rows(self):
        too_long = self.client.get(
            self._url("sales", start=self.today - timedelta(days=366), end=self.today)
        )
        maximum_range = self.client.get(
            self._url("sales", start=self.today - timedelta(days=365), end=self.today)
        )

        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(
            str(too_long.data["date"]),
            "Sana oralig‘i 366 kundan oshmasligi kerak.",
        )
        self.assertEqual(maximum_range.status_code, 200, maximum_range.data)
        self.assertEqual(len(maximum_range.data["rows"]), 366)

    def test_driver_and_shop_owner_are_forbidden_from_every_report(self):
        report_names = ("sales", "debtors", "drivers", "products")
        for user in (self.driver_user, self.owner):
            self.client.force_authenticate(user)
            for report_name in report_names:
                with self.subTest(role=user.role, report=report_name):
                    response = self.client.get(self._url(report_name))
                    self.assertEqual(response.status_code, 403)

    def test_csv_escapes_formula_prefixes_in_shop_names(self):
        ShopBalance.objects.create(
            company=self.company,
            shop=self.shop,
            current_balance=Decimal("100.00"),
        )
        for prefix in ("=", "+", "-", "@", "\t"):
            self.shop.name = f"{prefix}hisobot_test"
            self.shop.save(update_fields=("name", "updated_at"))
            response = self.client.get(self._url("debtors", export="csv"))
            rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))

            with self.subTest(prefix=repr(prefix)):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(rows[1][1].startswith("'"))
                self.assertEqual(rows[1][1], f"'{prefix}hisobot_test")

    def test_discounted_sales_total_matches_posted_delivery_debits(self):
        ShopPrice.objects.create(
            company=self.company,
            shop=self.shop,
            product=self.product,
            price=Decimal("2000.00"),
            discount_percent=Decimal("12.50"),
        )
        order = create_shop_order(
            user=self.owner,
            data={
                "company_id": self.company.pk,
                "delivery_date": self.today + timedelta(days=1),
                "items": [{"product_id": self.product.pk, "quantity": Decimal("2.00")}],
            },
        )
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal("1750.00"))

        order.status = Order.Status.IN_TRANSIT
        order.save(update_fields=("status", "updated_at"))
        transition_order(
            order=order,
            actor=self.admin,
            target=Order.Status.DELIVERED,
            reason="Hisobot sinovi uchun yetkazildi",
        )
        response = self.client.get(self._url("sales", start=self.today, end=self.today))

        delivered_order_ids = OrderStatusHistory.objects.filter(
            order__company=self.company,
            status=Order.Status.DELIVERED,
            created_at__date=self.today,
        ).values_list("order_id", flat=True)
        debit_total = BalanceEntry.objects.filter(
            company=self.company,
            order_id__in=delivered_order_ids,
            direction=BalanceEntry.Direction.DEBIT,
            posted_at__isnull=False,
        ).aggregate(total=Sum("amount"))["total"]

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(debit_total, Decimal("3500.00"))
        self.assertEqual(response.data["summary"]["delivered_amount"], str(debit_total))

    def test_reports_cannot_read_another_company(self):
        own_shop = ShopBalance.objects.create(
            company=self.company,
            shop=self.shop,
            current_balance=Decimal("10.00"),
        )
        ShopBalance.objects.create(
            company=self.other_company,
            shop=self.other_shop,
            current_balance=Decimal("9999.00"),
        )

        response = self.client.get(self._url("debtors"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [row["shop_id"] for row in response.data["debtors"]],
            [own_shop.shop_id],
        )
        self.client.force_authenticate(self.other_admin)
        other_response = self.client.get(self._url("debtors"))
        self.assertEqual(
            [row["shop_id"] for row in other_response.data["debtors"]],
            [self.other_shop.pk],
        )
