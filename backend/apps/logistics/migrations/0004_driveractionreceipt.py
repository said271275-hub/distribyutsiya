import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("logistics", "0003_driverprofile_vehicle_vehicle_volume_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverActionReceipt",
            fields=[
                ("action_id", models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ("action_type", models.CharField(max_length=16)),
                ("payload_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="driver_action_receipts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "stop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="driver_action_receipts",
                        to="logistics.tripstop",
                    ),
                ),
                (
                    "trip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="driver_action_receipts",
                        to="logistics.trip",
                    ),
                ),
            ],
        ),
    ]