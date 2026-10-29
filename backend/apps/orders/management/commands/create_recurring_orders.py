from django.core.management.base import BaseCommand

from apps.orders.recurring_services import create_recurring_drafts


class Command(BaseCommand):
    help = "Takroriy buyurtmalar uchun tasdiqlash kutilayotgan qoralamalarni yaratadi."

    def handle(self, *args, **options):
        created = create_recurring_drafts()
        self.stdout.write(f"Yaratilgan buyurtma qoralamalari: {created}")
