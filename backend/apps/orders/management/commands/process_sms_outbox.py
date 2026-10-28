import time

from django.core.management.base import BaseCommand, CommandError

from apps.orders.sms_notifications import process_pending_sms


class Command(BaseCommand):
    help = "Buyurtma SMS xabarlari navbatini qayta ishlaydi."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=float, default=1.0)
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        interval = options["interval"]
        limit = options["limit"]
        if interval <= 0 or limit <= 0:
            raise CommandError("--interval va --limit noldan katta bo‘lishi kerak.")

        while True:
            processed = process_pending_sms(limit=limit)
            if not options["loop"]:
                self.stdout.write(f"Qayta ishlangan SMS xabarlari: {processed}")
                return
            if processed == 0:
                time.sleep(interval)
