from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.logistics.models import DriverProfile, Vehicle


class Command(BaseCommand):
    help = "Demo kompaniya, katalog va transportni yaratadi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo-users",
            action="store_true",
            help="Sinov do‘konlari va xodimlarini ham yaratadi.",
        )
        parser.add_argument(
            "--with-demo-companies",
            action="store_true",
            help="2 ta qo‘shimcha faol demo kompaniya va ularning mahsulotlarini yaratadi.",
        )
        parser.add_argument(
            "--clean-demo-companies",
            action="store_true",
            help="Qo‘shimcha demo kompaniyalarni tozalaydi.",
        )
        parser.add_argument(
            "--archive-demo-products-only",
            action="store_true",
            help="Mavjud namuna mahsulotlarini arxivlaydi, boshqa namuna ma’lumotlarini yaratmaydi.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clean_demo_companies"]:
            demo_companies = Company.objects.filter(
                name__in=["Oazis Ichimliklari", "Baraka Savdo"]
            )
            Product.objects.filter(company__in=demo_companies).delete()
            CompanyShopLink.objects.filter(company__in=demo_companies).delete()
            deleted_count, _ = demo_companies.delete()
            self.stdout.write(
                self.style.SUCCESS(f"{deleted_count} ta qo‘shimcha demo kompaniya yozuvi tozalandi.")
            )
            return

        if options["archive_demo_products_only"]:
            company = Company.objects.filter(name="Sirdaryo Distribyutsiya").first()
            archived_products = 0
            if company is not None:
                archived_products = Product.objects.filter(
                    company=company,
                    name__startswith="Demo mahsulot ",
                    is_archived=False,
                ).update(is_active=False, is_archived=True)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{archived_products} ta namuna mahsuloti arxivlandi."
                )
            )
            return

        with_demo_users = options["with_demo_users"]
        with_demo_companies = options["with_demo_companies"]
        company, _ = Company.objects.get_or_create(
            name="Sirdaryo Distribyutsiya",
            defaults={
                "brand_color": "#1E88E5",
                "contact_phone": "+998900009900",
                "status": Company.Status.ACTIVE,
                "is_active": True,
            },
        )
        if company.status != Company.Status.ACTIVE:
            company.status = Company.Status.ACTIVE
            company.save(update_fields=("status",))
        archived_products = Product.objects.filter(
            company=company,
            name__startswith="Demo mahsulot ",
            is_archived=False,
        ).update(is_active=False, is_archived=True)

        demo_shops = 0
        demo_drivers = 0
        demo_dispatchers = 0
        if with_demo_users:
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
                CompanyShopLink.objects.get_or_create(
                    company=company,
                    shop=shop,
                    defaults={"status": CompanyShopLink.Status.ACTIVE, "is_active": True},
                )

            demo_shops = 20
        for index in range(1, 3):
            Vehicle.objects.get_or_create(
                company=company,
                plate_number=f"01A{index:03d}AA",
                defaults={
                    "name": f"Demo avtomobil {index}",
                    "capacity": Decimal("1500.00"),
                    "is_active": True,
                },
            )

        if with_demo_users:
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
            demo_drivers = 2
            demo_dispatchers = 1

        extra_companies_count = 0
        if with_demo_companies:
            oazis, _ = Company.objects.get_or_create(
                name="Oazis Ichimliklari",
                defaults={
                    "brand_color": "#00897B",
                    "contact_phone": "+998900009902",
                    "status": Company.Status.ACTIVE,
                    "is_active": True,
                    "description": "Salqin ichimliklar va tabiiy sharbatlar",
                },
            )
            Product.objects.get_or_create(
                company=oazis,
                name="Oazis Choy 1L",
                defaults={"unit": Product.Unit.BOX, "price": Decimal("12000.00"), "is_active": True},
            )
            Product.objects.get_or_create(
                company=oazis,
                name="Oazis Sharbat 1.5L",
                defaults={"unit": Product.Unit.BOX, "price": Decimal("16000.00"), "is_active": True},
            )

            baraka, _ = Company.objects.get_or_create(
                name="Baraka Savdo",
                defaults={
                    "brand_color": "#E65100",
                    "contact_phone": "+998900009903",
                    "status": Company.Status.ACTIVE,
                    "is_active": True,
                    "description": "Shirinlik va qandolat mahsulotlari",
                },
            )
            Product.objects.get_or_create(
                company=baraka,
                name="Baraka Shirinlik 1kg",
                defaults={"unit": Product.Unit.BOX, "price": Decimal("35000.00"), "is_active": True},
            )
            Product.objects.get_or_create(
                company=baraka,
                name="Baraka Shokolad 200g",
                defaults={"unit": Product.Unit.PIECE, "price": Decimal("18000.00"), "is_active": True},
            )

            for s in Shop.objects.all():
                CompanyShopLink.objects.get_or_create(
                    company=oazis,
                    shop=s,
                    defaults={"status": CompanyShopLink.Status.ACTIVE, "is_active": True},
                )
                CompanyShopLink.objects.get_or_create(
                    company=baraka,
                    shop=s,
                    defaults={"status": CompanyShopLink.Status.ACTIVE, "is_active": True},
                )
            extra_companies_count = 2

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed tayyor: {1 + extra_companies_count} kompaniya, {archived_products} demo mahsulot arxivlandi, "
                f"{demo_shops} do‘kon, "
                f"2 mashina, {demo_drivers} haydovchi va {demo_dispatchers} dispetcher."
            )
        )
