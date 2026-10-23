from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from apps.accounts.models import (
    DeletionRequest,
    LoginAttempt,
    PhoneOTP,
    PhoneOTPSendWindow,
    User,
)
from apps.audit.models import AuditLog
from apps.catalog.models import ContainerMovement, Product, ReturnableContainer
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.logistics.models import DriverProfile, Trip, TripStop, TripStopOrder, Vehicle
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import BalanceEntry, Payment, ShopBalance


class Command(BaseCommand):
    help = "Lokal sinov foydalanuvchilari va ularga tegishli ma’lumotlarni tozalaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes-delete-everything",
            action="store_true",
            help="O‘chirishni davom ettirishdan oldin DELETE tasdig‘ini so‘raydi.",
        )

    def _counts(self):
        return {
            "foydalanuvchi": User.objects.count(),
            "do‘kon": Shop.objects.count(),
            "buyurtma": Order.objects.count(),
            "reys": Trip.objects.count(),
            "reys to‘xtashi": TripStop.objects.count(),
            "buyurtma bandi": OrderItem.objects.count(),
            "buyurtma holati tarixi": OrderStatusHistory.objects.count(),
            "to‘lov": Payment.objects.count(),
            "qarz yozuvi": BalanceEntry.objects.count(),
            "do‘kon balansi": ShopBalance.objects.count(),
            "tara harakati": ContainerMovement.objects.count(),
            "audit yozuvi": AuditLog.objects.count(),
            "o‘chirish so‘rovi": DeletionRequest.objects.count(),
            "yangilash tokeni": OutstandingToken.objects.count(),
            "qora ro‘yxat tokeni": BlacklistedToken.objects.count(),
            "reys-to‘xtash buyurtma bog‘lanishi": TripStopOrder.objects.count(),
            "do‘kon-kompaniya bog‘lanishi": CompanyShopLink.objects.count(),
            "do‘kon narxi": ShopPrice.objects.count(),
            "haydovchi profili": DriverProfile.objects.count(),
            "kirish urinishlari": LoginAttempt.objects.count(),
            "telefon tasdiq kodi": PhoneOTP.objects.count(),
            "kod yuborish oynasi": PhoneOTPSendWindow.objects.count(),
        }

    def _write_counts(self, title, counts):
        self.stdout.write(title)
        for label, count in counts.items():
            self.stdout.write(f"  {label}: {count}")

    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.DEV_OTP_ENABLED:
            raise CommandError(
                "Bu buyruq faqat DEBUG=True va DEV_OTP_ENABLED=True bo‘lgan mahalliy muhitda ishlaydi."
            )

        counts = self._counts()
        if not options["yes_delete_everything"]:
            self._write_counts(
                "Quruq sinov: quyidagi yozuvlar o‘chiriladi; hozircha hech narsa o‘chirilmadi.",
                counts,
            )
            self.stdout.write(
                f"Qoladi: {Company.objects.count()} kompaniya, "
                f"{Product.objects.count()} mahsulot, {Vehicle.objects.count()} mashina, "
                f"{ReturnableContainer.objects.count()} tara turi."
            )
            self.stdout.write("Haqiqiy o‘chirish uchun --yes-delete-everything bering.")
            return

        self.stdout.write("Davom etish uchun DELETE deb yozing.")
        if input().strip() != "DELETE":
            raise CommandError("Tasdiq mos kelmadi; hech narsa o‘chirilmadi.")

        with transaction.atomic():
            DeletionRequest.objects.all().delete()
            AuditLog.objects.all().delete()
            BlacklistedToken.objects.all().delete()
            OutstandingToken.objects.all().delete()
            PhoneOTP.objects.all().delete()
            PhoneOTPSendWindow.objects.all().delete()
            LoginAttempt.objects.all().delete()
            ContainerMovement.objects.all().delete()
            BalanceEntry.objects.all().delete()
            Payment.objects.all().delete()
            ShopBalance.objects.all().delete()
            TripStopOrder.objects.all().delete()
            Trip.objects.all().delete()
            Order.objects.all().delete()
            ShopPrice.objects.all().delete()
            CompanyShopLink.objects.all().delete()
            DriverProfile.objects.all().delete()
            Shop.objects.all().delete()
            User.objects.all().delete()

        self._write_counts("O‘chirildi (yozuvlar soni):", counts)
        self.stdout.write(
            f"Qoladi: {Company.objects.count()} kompaniya, "
            f"{Product.objects.count()} mahsulot, {Vehicle.objects.count()} mashina, "
            f"{ReturnableContainer.objects.count()} tara turi."
        )
