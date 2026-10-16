from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import DeletionRequest, LoginAttempt, PhoneOTP
from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = "30 kunlik muddati tugagan akkauntlarni anonimlashtiradi."

    def handle(self, *args, **options):
        due_ids = list(
            DeletionRequest.objects.filter(
                status=DeletionRequest.Status.PENDING,
                scheduled_for__lte=timezone.now(),
            ).values_list("id", flat=True)
        )
        processed = 0
        for deletion_id in due_ids:
            with transaction.atomic():
                deletion = (
                    DeletionRequest.objects.select_for_update()
                    .select_related("user")
                    .filter(
                        pk=deletion_id,
                        status=DeletionRequest.Status.PENDING,
                        scheduled_for__lte=timezone.now(),
                    )
                    .first()
                )
                if deletion is None:
                    continue

                user = deletion.user
                for shop in user.shops.select_for_update().all():
                    shop.name = f"O‘chirilgan do‘kon #{shop.pk}"
                    shop.phone_primary = f"deleted-shop-{shop.pk}"
                    shop.phone_secondary = ""
                    shop.address = "Ma’lumotlar o‘chirildi"
                    shop.district = ""
                    shop.status = shop.Status.ARCHIVED
                    shop.save(
                        update_fields=(
                            "name", "phone_primary", "phone_secondary", "address",
                            "district", "status", "updated_at",
                        )
                    )

                original_phone = user.phone
                user.phone = f"deleted-user-{user.pk}"
                user.set_unusable_password()
                user.last_login = None
                user.is_active = False
                user.is_blocked = True
                user.is_deleted = True
                user.auth_version += 1
                user.save(
                    update_fields=(
                        "phone", "password", "last_login", "is_active",
                        "is_blocked", "is_deleted", "auth_version",
                    )
                )
                PhoneOTP.objects.filter(phone=original_phone).delete()
                LoginAttempt.objects.filter(phone=original_phone).delete()
                deletion.reason_other = ""
                deletion.status = DeletionRequest.Status.COMPLETED
                deletion.processed_at = timezone.now()
                deletion.save(
                    update_fields=("reason_other", "status", "processed_at")
                )
                AuditLog.objects.create(
                    actor=None,
                    company=user.company,
                    action="account_anonymized",
                    entity_type="User",
                    entity_id=str(user.pk),
                )
                processed += 1

        self.stdout.write(self.style.SUCCESS(f"Anonimlashtirildi: {processed} akkaunt."))
