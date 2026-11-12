from django.core.management.base import BaseCommand
from django.db import transaction

from apps.companies.models import Company


class Command(BaseCommand):
    help = "2 ta qo‘shimcha demo kompaniya va ularning ma’lumotlarini tozalaydi."

    @transaction.atomic
    def handle(self, *args, **options):
        demo_companies = Company.objects.filter(name__in=["Oazis Ichimliklari", "Baraka Savdo"])
        from apps.catalog.models import Product
        from apps.companies.models import CompanyShopLink

        Product.objects.filter(company__in=demo_companies).delete()
        CompanyShopLink.objects.filter(company__in=demo_companies).delete()
        deleted_count, _ = demo_companies.delete()
        self.stdout.write(
            self.style.SUCCESS(f"{deleted_count} ta demo kompaniya va bog‘langan yozuvlar tozalandi.")
        )

