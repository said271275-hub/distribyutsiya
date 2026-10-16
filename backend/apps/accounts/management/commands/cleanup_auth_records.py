from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import LoginAttempt, PhoneOTP, PhoneOTPSendWindow


class Command(BaseCommand):
    help = "Muddati o‘tgan OTP va login urinish yozuvlarini tozalaydi."

    def handle(self, *args, **options):
        now = timezone.now()
        deleted_otps, _ = PhoneOTP.objects.filter(
            expires_at__lte=now - timedelta(days=1)
        ).delete()
        deleted_attempts, _ = LoginAttempt.objects.filter(
            updated_at__lte=now - timedelta(days=30),
            blocked_until__isnull=True,
        ).delete()
        deleted_windows, _ = PhoneOTPSendWindow.objects.filter(
            window_started_at__lte=now - timedelta(days=1)
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tozalandi: {deleted_otps} OTP, {deleted_attempts} login urinish, "
                f"{deleted_windows} OTP limit oynasi."
            )
        )
