from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, Shop
from apps.logistics.models import DriverProfile, Vehicle


class DemoSeedCommandTests(TestCase):
    def test_seed_creates_expected_demo_data_and_is_idempotent(self):
        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", stdout=StringIO())

        company = Company.objects.get(name="Sirdaryo Distribyutsiya")
        self.assertEqual(Product.objects.filter(company=company).count(), 10)
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
