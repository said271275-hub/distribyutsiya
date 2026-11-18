from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.logistics.models import DriverProfile, Vehicle


class Command(BaseCommand):
    help = "Pepsi kompaniyasi, Sayhun do'koni va Ruslan haydovchisini yaratadi/yangilaydi."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Kompaniya: Pepsi
        pepsi, _ = Company.objects.update_or_create(
            name="Pepsi",
            defaults={
                "status": Company.Status.ACTIVE,
                "is_active": True,
                "tax_id": "933318407",
                "contact_phone": "+998933318407",
                "brand_color": "#004B93",
                "description": "Pepsi rasmiy distribyutsiyasi",
                "auto_approve_subscriptions": True,
            },
        )

        # 2. Kompaniya Admin / Dispetcher: +998933318407
        admin_user, _ = User.objects.get_or_create(
            phone="+998933318407",
            defaults={
                "company": pepsi,
                "role": User.Role.COMPANY_ADMIN,
                "is_active": True,
                "must_change_password": False,
            },
        )
        admin_user.company = pepsi
        admin_user.role = User.Role.COMPANY_ADMIN
        admin_user.is_active = True
        admin_user.is_blocked = False
        admin_user.is_deleted = False
        admin_user.must_change_password = False
        admin_user.set_password("hojiakbar123")
        admin_user.save()

        # 3. Do'kon egasi: +998508555440
        shop_owner, _ = User.objects.get_or_create(
            phone="+998508555440",
            defaults={
                "role": User.Role.SHOP_OWNER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        shop_owner.role = User.Role.SHOP_OWNER
        shop_owner.is_active = True
        shop_owner.is_blocked = False
        shop_owner.is_deleted = False
        shop_owner.must_change_password = False
        shop_owner.set_password("hojiakbar123")
        shop_owner.save()

        # 4. Do'kon: Sayhun
        sayhun, _ = Shop.objects.update_or_create(
            owner=shop_owner,
            defaults={
                "name": "Sayhun",
                "owner_name": "Sayhun Do'koni",
                "phone_primary": "+998508555440",
                "address": "Sayhunobod tumani, Markaz",
                "district": "Sayhunobod",
                "latitude": Decimal("40.500000"),
                "longitude": Decimal("68.800000"),
                "status": Shop.Status.ACTIVE,
                "sms_notifications_enabled": True,
            },
        )

        # 5. Bog'lanish: Pepsi <-> Sayhun
        CompanyShopLink.objects.update_or_create(
            company=pepsi,
            shop=sayhun,
            defaults={
                "status": CompanyShopLink.Status.ACTIVE,
                "is_active": True,
            },
        )

        # 6. Haydovchi: Ruslan (+998883401015)
        driver_user, _ = User.objects.get_or_create(
            phone="+998883401015",
            defaults={
                "company": pepsi,
                "role": User.Role.DRIVER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        driver_user.company = pepsi
        driver_user.role = User.Role.DRIVER
        driver_user.is_active = True
        driver_user.is_blocked = False
        driver_user.is_deleted = False
        driver_user.must_change_password = False
        driver_user.set_password("hojiakbar123")
        driver_user.save()

        # 7. Mashina va haydovchi profili
        vehicle, _ = Vehicle.objects.update_or_create(
            company=pepsi,
            plate_number="20A777AA",
            defaults={
                "name": "Isuzu Pepsi",
                "capacity": Decimal("3500.00"),
                "is_active": True,
            },
        )
        DriverProfile.objects.update_or_create(
            user=driver_user,
            defaults={
                "company": pepsi,
                "vehicle": vehicle,
                "license_number": "AB1234567",
            },
        )

        # 8. Mahsulotlar
        products_data = [
            ("Pepsi 1.5L", Product.Unit.BOX, Decimal("14000.00")),
            ("Pepsi 0.5L", Product.Unit.BOX, Decimal("8000.00")),
            ("Mirinda 1.5L", Product.Unit.BOX, Decimal("14000.00")),
            ("7UP 1.5L", Product.Unit.BOX, Decimal("14000.00")),
        ]
        for p_name, p_unit, p_price in products_data:
            Product.objects.update_or_create(
                company=pepsi,
                name=p_name,
                defaults={
                    "unit": p_unit,
                    "price": p_price,
                    "is_active": True,
                    "is_archived": False,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Muvaffaqiyatli yaratildi: Pepsi (+998933318407), Sayhun (+998508555440), Ruslan (+998883401015)."
            )
        )
