from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.companies.models import Company, Shop, CompanyShopLink
from apps.logistics.models import Vehicle, DriverProfile
from apps.catalog.models import Product, Category


class Command(BaseCommand):
    help = "Demo ma'lumotlarni yaratadi yoki yangilaydi (fanta, haydovchi fazliddin, do'konlar one23 va fma222.uz)."

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. Kompaniya: fanta
            fanta, _ = Company.objects.get_or_create(
                name="fanta",
                defaults={
                    "status": Company.Status.ACTIVE,
                    "is_active": True,
                    "contact_phone": "+998882752775",
                    "description": "Fanta yaxna ichimliklar distribyutsiyasi",
                    "service_districts": ["Chilonzor", "Yunusobod", "Mirobod", "Yashnobod", "Olmazor"],
                }
            )
            fanta.status = Company.Status.ACTIVE
            fanta.is_active = True
            fanta.save()

            # Fanta admin
            fanta_admin, _ = User.objects.get_or_create(
                phone="+998882752775",
                defaults={
                    "role": User.Role.COMPANY_ADMIN,
                    "company": fanta,
                    "is_active": True,
                }
            )
            fanta_admin.role = User.Role.COMPANY_ADMIN
            fanta_admin.company = fanta
            fanta_admin.is_active = True
            fanta_admin.set_password("hojiakbar123")
            fanta_admin.save()

            # 2. Haydovchi: fazliddin (+998949110427)
            driver_user, _ = User.objects.get_or_create(
                phone="+998949110427",
                defaults={
                    "role": User.Role.DRIVER,
                    "company": fanta,
                    "is_active": True,
                }
            )
            driver_user.role = User.Role.DRIVER
            driver_user.company = fanta
            driver_user.is_active = True
            driver_user.set_password("hojiakbar123")
            driver_user.save()

            vehicle, _ = Vehicle.objects.get_or_create(
                company=fanta,
                plate_number="01A777FA",
                defaults={
                    "name": "Labo (Fazliddin)",
                    "capacity": 1000,
                    "is_active": True,
                }
            )

            driver_profile, _ = DriverProfile.objects.get_or_create(
                user=driver_user,
                defaults={
                    "company": fanta,
                    "vehicle": vehicle,
                    "license_number": "AB9491104",
                }
            )
            driver_profile.company = fanta
            driver_profile.vehicle = vehicle
            driver_profile.save()

            # 3. Do'kon: one23 (+998880382775)
            shop1_user, _ = User.objects.get_or_create(
                phone="+998880382775",
                defaults={
                    "role": User.Role.SHOP_OWNER,
                    "is_active": True,
                }
            )
            shop1_user.role = User.Role.SHOP_OWNER
            shop1_user.company = None
            shop1_user.is_active = True
            shop1_user.set_password("hojiakabr123")
            shop1_user.save()

            shop1, _ = Shop.objects.get_or_create(
                owner=shop1_user,
                defaults={
                    "name": "one23",
                    "phone_primary": "+998880382775",
                    "owner_name": "Do‘konchi",
                    "address": "Toshkent sh., Chilonzor tumani, 9-mavze",
                    "district": "Chilonzor",
                    "latitude": 41.285830,
                    "longitude": 69.203560,
                    "status": Shop.Status.ACTIVE,
                }
            )
            shop1.name = "one23"
            shop1.phone_primary = "+998880382775"
            shop1.status = Shop.Status.ACTIVE
            shop1.save()

            # 4. Do'kon: fma222.uz (+998934200753)
            shop2_user, _ = User.objects.get_or_create(
                phone="+998934200753",
                defaults={
                    "role": User.Role.SHOP_OWNER,
                    "is_active": True,
                }
            )
            shop2_user.role = User.Role.SHOP_OWNER
            shop2_user.company = None
            shop2_user.is_active = True
            shop2_user.set_password("hojiakabr123")
            shop2_user.save()

            shop2, _ = Shop.objects.get_or_create(
                owner=shop2_user,
                defaults={
                    "name": "fma222.uz",
                    "phone_primary": "+998934200753",
                    "owner_name": "Do‘konchi",
                    "address": "Toshkent sh., Yunusobod tumani, 4-mavze",
                    "district": "Yunusobod",
                    "latitude": 41.365830,
                    "longitude": 69.283560,
                    "status": Shop.Status.ACTIVE,
                }
            )
            shop2.name = "fma222.uz"
            shop2.phone_primary = "+998934200753"
            shop2.status = Shop.Status.ACTIVE
            shop2.save()

            # 5. Bog'lanishlar (CompanyShopLink)
            all_companies = list(Company.objects.filter(is_active=True))
            all_shops = list(Shop.objects.filter(status=Shop.Status.ACTIVE))

            for comp in all_companies:
                for sh in all_shops:
                    link, _ = CompanyShopLink.objects.get_or_create(
                        company=comp,
                        shop=sh,
                        defaults={
                            "status": CompanyShopLink.Status.ACTIVE,
                            "is_active": True,
                        }
                    )
                    link.status = CompanyShopLink.Status.ACTIVE
                    link.is_active = True
                    link.save()

            # 6. Mahsulotlar
            category, _ = Category.objects.get_or_create(
                company=fanta,
                name="Ichimliklar",
            )
            fanta_products = [
                ("Fanta Orange 0.5L", "7000.00", "piece"),
                ("Fanta Orange 1.0L", "11000.00", "piece"),
                ("Fanta Orange 1.5L", "14000.00", "piece"),
            ]
            for p_name, p_price, p_unit in fanta_products:
                Product.objects.get_or_create(
                    company=fanta,
                    name=p_name,
                    defaults={
                        "category": category,
                        "base_price": p_price,
                        "unit": p_unit,
                        "is_active": True,
                    }
                )

        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar muvaffaqiyatli saqlandi!"))
