from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, Shop
from apps.logistics.models import DriverProfile, Vehicle
from apps.orders.models import Order, OrderItem


class DemoSeedCommandTests(TestCase):
    @override_settings(
        DEBUG=True,
        DEV_OTP_ENABLED=True,
        DEV_STAFF_PASSWORD="Demo-staff-password-123!",
    )
    def test_seed_does_not_create_users_without_demo_users_flag(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        call_command("seed_demo", stdout=StringIO())

        company = Company.objects.get(name="Sirdaryo Distribyutsiya")
        self.assertEqual(Product.objects.filter(company=company).count(), 10)
        self.assertEqual(Vehicle.objects.filter(company=company).count(), 2)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Shop.objects.exists())
        self.assertIn("0 do‘kon", output.getvalue())
        self.assertIn("0 haydovchi", output.getvalue())

    def test_seed_creates_expected_demo_data_and_is_idempotent(self):
        call_command("seed_demo", "--with-demo-users", stdout=StringIO())
        call_command("seed_demo", "--with-demo-users", stdout=StringIO())

        company = Company.objects.get(name="Sirdaryo Distribyutsiya")
        products = list(Product.objects.filter(company=company))
        self.assertEqual(len(products), 10)
        self.assertTrue(all(product.unit_weight is not None for product in products))
        self.assertTrue(all(product.unit_volume is not None for product in products))
        self.assertTrue(all(product.unit_weight > 0 for product in products))
        self.assertTrue(all(product.unit_volume > 0 for product in products))
        self.assertEqual(
            Shop.objects.filter(company_links__company=company).distinct().count(), 20
        )
        shops = Shop.objects.filter(company_links__company=company)
        self.assertTrue(all(40 <= shop.latitude <= 42 for shop in shops))
        self.assertTrue(all(66 <= shop.longitude <= 69 for shop in shops))
        self.assertEqual(Vehicle.objects.filter(company=company).count(), 2)
        self.assertEqual(DriverProfile.objects.filter(company=company).count(), 2)
        self.assertEqual(
            User.objects.filter(company=company, role=User.Role.COMPANY_ADMIN).count(), 1
        )

    def test_demo_product_loads_split_nearby_orders_into_two_trips(self):
        call_command("seed_demo", "--with-demo-users", stdout=StringIO())
        company = Company.objects.get(name="Sirdaryo Distribyutsiya")
        product = Product.objects.get(company=company, name="Demo mahsulot 02")
        shops = list(
            Shop.objects.filter(
                company_links__company=company,
                phone_primary__in=("+998900020001", "+998900020011"),
            ).order_by("phone_primary")
        )
        self.assertEqual(len(shops), 2)
        admin = User.objects.get(phone="+998900009901")
        delivery_date = date.today() + timedelta(days=1)
        for shop in shops:
            order = Order.objects.create(
                company=company,
                shop=shop,
                status=Order.Status.CONFIRMED,
                delivery_date=delivery_date,
            )
            OrderItem.objects.create(
                company=company,
                order=order,
                product=product,
                quantity=Decimal("40.00"),
                unit_price=product.price,
            )
            order.recalculate_total()

        client = APIClient()
        client.force_authenticate(admin)
        response = client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": delivery_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["trips"]), 2)
        self.assertEqual(
            [trip["estimated_load"] for trip in response.data["trips"]],
            [Decimal("800.00000"), Decimal("800.00000")],
        )
        self.assertEqual(response.data["unassigned_orders"], [])

    @override_settings(
        DEBUG=True,
        DEV_OTP_ENABLED=True,
        DEV_STAFF_PASSWORD="Demo-staff-password-123!",
    )
    def test_seed_staff_can_login_with_configured_local_password(self):
        call_command("seed_demo", "--with-demo-users", stdout=StringIO())

        user = User.objects.get(phone="+998900009901")
        self.assertTrue(user.check_password("Demo-staff-password-123!"))
        response = APIClient().post(
            "/api/auth/staff/login/",
            {"phone": user.phone, "password": "Demo-staff-password-123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
