from django.db import migrations, models


def require_staff_password_change(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role__in=("company_admin", "driver")).update(
        must_change_password=True
    )


def undo_staff_password_change(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role__in=("company_admin", "driver")).update(
        must_change_password=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_alter_phoneotp_purpose"),
    ]

    operations = [
        migrations.AlterField(
            model_name="phoneotp",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("registration", "Ro‘yxatdan o‘tish"),
                    ("password_reset", "Parolni tiklash"),
                    ("phone_change", "Telefon raqamini o‘zgartirish"),
                    ("account_deletion", "Akkauntni o‘chirish"),
                ],
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                verbose_name="Birinchi kirishda parolni almashtirish",
            ),
        ),
        migrations.RunPython(
            require_staff_password_change,
            undo_staff_password_change,
        ),
    ]
