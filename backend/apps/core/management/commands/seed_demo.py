from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.logistics.models import DriverProfile, Vehicle


class Command(BaseCommand):
    help = "Demo kompaniya, katalog, do‘konlar, transport va xodimlarni yaratadi."

    @transaction.atomic
    def handle(self, *args, **options):
        company, _ = Company.objects.get_or_create(
            name="Sirdaryo Distribyutsiya",
            defaults={
                "brand_color": "#1E88E5",
                "contact_phone": "+998900009900",
                "is_active": True,
            },
        )
        units = (Product.Unit.PIECE, Product.Unit.BOX, Product.Unit.BLOCK)
        for index in range(1, 11):
            defaults = {
                "unit": units[(index - 1) % len(units)],
                "price": Decimal(15000 + index * 2500),
                "unit_weight": Decimal("20.000"),
                "unit_volume": Decimal("0.080"),
                "is_active": True,
            }
            product, created = Product.objects.get_or_create(
                company=company,
                name=f"Demo mahsulot {index:02d}",
                defaults=defaults,
            )
            if not created:
                updates = {}
                if product.unit_weight is None:
                    updates["unit_weight"] = defaults["unit_weight"]
                if product.unit_volume is None:
                    updates["unit_volume"] = defaults["unit_volume"]
                if updates:
                    Product.objects.filter(pk=product.pk).update(**updates)

        districts = (
            "Guliston", "Yangiyer", "Shirin", "Boyovut", "Sayxunobod",
            "Mirzaobod", "Oqoltin", "Sardoba", "Xovos", "Sirdaryo",
        )
        for index in range(1, 21):
            owner, _ = User.objects.get_or_create(
                phone=f"+99890001{index:04d}",
                defaults={"role": User.Role.SHOP_OWNER, "is_active": True},
            )
            shop, _ = Shop.objects.get_or_create(
                phone_primary=f"+99890002{index:04d}",
                defaults={
                    "owner": owner,
                    "name": f"Demo do‘kon {index:02d}",
                    "phone_secondary": "",
                    "address": f"{districts[(index - 1) % len(districts)]} tumani, markaz",
                    "district": districts[(index - 1) % len(districts)],
                    "latitude": Decimal("40.840000") + Decimal(index % 10) * Decimal("0.012000"),
                    "longitude": Decimal("68.660000") + Decimal(index // 10) * Decimal("0.018000"),
                    "status": Shop.Status.ACTIVE,
                },
            )
            CompanyShopLink.objects.get_or_create(company=company, shop=shop)

        for index in range(1, 3):
            phone = f"+99890003{index:04d}"
            driver, _ = User.objects.get_or_create(
                phone=phone,
                defaults={
                    "company": company,
                    "role": User.Role.DRIVER,
                    "is_active": True,
                },
            )
            if settings.DEV_STAFF_PASSWORD:
                driver.set_password(settings.DEV_STAFF_PASSWORD)
                driver.save(update_fields=("password",))
            DriverProfile.objects.get_or_create(
                company=company, user=driver, defaults={"license_number": ""}
            )
            Vehicle.objects.get_or_create(
                company=company,
                plate_number=f"01A{index:03d}AA",
                defaults={
                    "name": f"Demo avtomobil {index}",
                    "capacity": Decimal("1500.00"),
                    "is_active": True,
                },
            )

        User.objects.get_or_create(
            phone="+998900009901",
            defaults={
                "company": company,
                "role": User.Role.COMPANY_ADMIN,
                "is_active": True,
            },
        )
        dispatcher = User.objects.get(phone="+998900009901")
        if settings.DEV_STAFF_PASSWORD:
            dispatcher.set_password(settings.DEV_STAFF_PASSWORD)
            dispatcher.save(update_fields=("password",))
        self.stdout.write(
            self.style.SUCCESS(
                "Seed tayyor: 1 kompaniya, 10 mahsulot, 20 do‘kon, "
                "2 mashina, 2 haydovchi va 1 dispetcher. "
                "Xodimlar: dispetcher +998900009901; haydovchilar "
                "+998900030001 va +998900030002."
            )
        )
