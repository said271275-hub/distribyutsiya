from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.logistics.models import DriverProfile, Vehicle


class Command(BaseCommand):
    help = "Fanta va Pepsi kompaniyalari, do'konlar (one23, fma222.uz, Sayhun) va haydovchilarni yaratadi/yangilaydi."

    @transaction.atomic
    def handle(self, *args, **options):
        # ==========================================
        # 1. KOMPANIYA: FANTA (+998882752775)
        # ==========================================
        fanta, _ = Company.objects.update_or_create(
            name="fanta",
            defaults={
                "status": Company.Status.ACTIVE,
                "is_active": True,
                "contact_phone": "+998882752775",
                "description": "Fanta rasmiy distribyutsiyasi",
                "auto_approve_subscriptions": True,
            },
        )

        fanta_admin, _ = User.objects.get_or_create(
            phone="+998882752775",
            defaults={
                "company": fanta,
                "role": User.Role.COMPANY_ADMIN,
                "is_active": True,
                "must_change_password": False,
            },
        )
        fanta_admin.company = fanta
        fanta_admin.role = User.Role.COMPANY_ADMIN
        fanta_admin.is_active = True
        fanta_admin.is_blocked = False
        fanta_admin.is_deleted = False
        fanta_admin.must_change_password = False
        fanta_admin.set_password("hojiakbar123")
        fanta_admin.save()

        # Haydovchi: Fazliddin (+998949110427)
        fazliddin_user, _ = User.objects.get_or_create(
            phone="+998949110427",
            defaults={
                "company": fanta,
                "role": User.Role.DRIVER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        fazliddin_user.company = fanta
        fazliddin_user.role = User.Role.DRIVER
        fazliddin_user.is_active = True
        fazliddin_user.is_blocked = False
        fazliddin_user.is_deleted = False
        fazliddin_user.must_change_password = False
        fazliddin_user.set_password("hojiakbar123")
        fazliddin_user.save()

        vehicle_fanta, _ = Vehicle.objects.update_or_create(
            company=fanta,
            plate_number="01A777FA",
            defaults={
                "name": "Labo Fanta",
                "capacity": Decimal("1000.00"),
                "is_active": True,
            },
        )
        DriverProfile.objects.update_or_create(
            user=fazliddin_user,
            defaults={
                "company": fanta,
                "vehicle": vehicle_fanta,
                "license_number": "AB9491104",
            },
        )

        # Fanta mahsulotlari
        for p_name, p_unit, p_price in [
            ("Fanta Orange 1.5L", Product.Unit.BOX, Decimal("14000.00")),
            ("Fanta Orange 0.5L", Product.Unit.BOX, Decimal("8000.00")),
            ("Fanta Tropical 1.5L", Product.Unit.BOX, Decimal("14000.00")),
        ]:
            Product.objects.update_or_create(
                company=fanta,
                name=p_name,
                defaults={
                    "unit": p_unit,
                    "price": p_price,
                    "is_active": True,
                    "is_archived": False,
                },
            )

        # ==========================================
        # 2. DO'KON 1: ONE23 (+998880382775)
        # ==========================================
        shop_owner_1, _ = User.objects.get_or_create(
            phone="+998880382775",
            defaults={
                "role": User.Role.SHOP_OWNER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        shop_owner_1.role = User.Role.SHOP_OWNER
        shop_owner_1.company = None
        shop_owner_1.is_active = True
        shop_owner_1.is_blocked = False
        shop_owner_1.is_deleted = False
        shop_owner_1.must_change_password = False
        shop_owner_1.set_password("hojiakabr123")
        shop_owner_1.save()

        shop_one23, _ = Shop.objects.update_or_create(
            owner=shop_owner_1,
            defaults={
                "name": "one23",
                "owner_name": "one23 Do'koni",
                "phone_primary": "+998880382775",
                "address": "Chilonzor tumani, 9-mavze",
                "district": "Chilonzor",
                "latitude": Decimal("41.285830"),
                "longitude": Decimal("69.203560"),
                "status": Shop.Status.ACTIVE,
                "sms_notifications_enabled": True,
            },
        )

        # ==========================================
        # 3. DO'KON 2: FMA222.UZ (+998934200753)
        # ==========================================
        shop_owner_2, _ = User.objects.get_or_create(
            phone="+998934200753",
            defaults={
                "role": User.Role.SHOP_OWNER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        shop_owner_2.role = User.Role.SHOP_OWNER
        shop_owner_2.company = None
        shop_owner_2.is_active = True
        shop_owner_2.is_blocked = False
        shop_owner_2.is_deleted = False
        shop_owner_2.must_change_password = False
        shop_owner_2.set_password("hojiakabr123")
        shop_owner_2.save()

        shop_fma222, _ = Shop.objects.update_or_create(
            owner=shop_owner_2,
            defaults={
                "name": "fma222.uz",
                "owner_name": "fma222 Do'koni",
                "phone_primary": "+998934200753",
                "address": "Yunusobod tumani, 4-mavze",
                "district": "Yunusobod",
                "latitude": Decimal("41.365830"),
                "longitude": Decimal("69.283560"),
                "status": Shop.Status.ACTIVE,
                "sms_notifications_enabled": True,
            },
        )

        # ==========================================
        # 4. MAVJUD PEPSI VA SAYHUN DO'KONI
        # ==========================================
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

        admin_pepsi, _ = User.objects.get_or_create(
            phone="+998933318407",
            defaults={
                "company": pepsi,
                "role": User.Role.COMPANY_ADMIN,
                "is_active": True,
                "must_change_password": False,
            },
        )
        admin_pepsi.company = pepsi
        admin_pepsi.role = User.Role.COMPANY_ADMIN
        admin_pepsi.is_active = True
        admin_pepsi.set_password("hojiakbar123")
        admin_pepsi.save()

        sayhun_owner, _ = User.objects.get_or_create(
            phone="+998508555440",
            defaults={
                "role": User.Role.SHOP_OWNER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        sayhun_owner.role = User.Role.SHOP_OWNER
        sayhun_owner.is_active = True
        sayhun_owner.set_password("hojiakbar123")
        sayhun_owner.save()

        shop_sayhun, _ = Shop.objects.update_or_create(
            owner=sayhun_owner,
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

        driver_ruslan, _ = User.objects.get_or_create(
            phone="+998883401015",
            defaults={
                "company": pepsi,
                "role": User.Role.DRIVER,
                "is_active": True,
                "must_change_password": False,
            },
        )
        driver_ruslan.company = pepsi
        driver_ruslan.role = User.Role.DRIVER
        driver_ruslan.is_active = True
        driver_ruslan.set_password("hojiakbar123")
        driver_ruslan.save()

        vehicle_pepsi, _ = Vehicle.objects.update_or_create(
            company=pepsi,
            plate_number="20A777AA",
            defaults={
                "name": "Isuzu Pepsi",
                "capacity": Decimal("3500.00"),
                "is_active": True,
            },
        )
        DriverProfile.objects.update_or_create(
            user=driver_ruslan,
            defaults={
                "company": pepsi,
                "vehicle": vehicle_pepsi,
                "license_number": "AB1234567",
            },
        )

        for p_name, p_unit, p_price in [
            ("Pepsi 1.5L", Product.Unit.BOX, Decimal("14000.00")),
            ("Pepsi 0.5L", Product.Unit.BOX, Decimal("8000.00")),
            ("Mirinda 1.5L", Product.Unit.BOX, Decimal("14000.00")),
            ("7UP 1.5L", Product.Unit.BOX, Decimal("14000.00")),
        ]:
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

        # ==========================================
        # 5. OBUNALAR (Barcha do'konlarni ikkala kompaniya bilan bog'lash)
        # ==========================================
        companies = [fanta, pepsi]
        shops = [shop_one23, shop_fma222, shop_sayhun]

        for c in companies:
            for s in shops:
                CompanyShopLink.objects.update_or_create(
                    company=c,
                    shop=s,
                    defaults={
                        "status": CompanyShopLink.Status.ACTIVE,
                        "is_active": True,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Muvaffaqiyatli saqlandi:\n"
                "- Firma: Fanta (+998882752775 / hojiakbar123)\n"
                "- Haydovchi: Fazliddin (+998949110427 / hojiakbar123)\n"
                "- Do'kon: one23 (+998880382775 / hojiakabr123)\n"
                "- Do'kon: fma222.uz (+998934200753 / hojiakabr123)"
            )
        )
