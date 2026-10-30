from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.accounts.services import normalize_uz_phone
from apps.audit.models import AuditLog
from apps.companies.models import Company


class Command(BaseCommand):
    help = "Kompaniya va uning birinchi administratorini yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Kompaniya nomi.")
        parser.add_argument("--admin-phone", required=True, help="Administrator telefoni.")

    def handle(self, *args, **options):
        name = options["name"].strip()
        if not name or len(name) > 200:
            raise CommandError("Kompaniya nomi 1 dan 200 tagacha belgidan iborat bo‘lishi kerak.")

        try:
            phone = normalize_uz_phone(options["admin_phone"])
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        company = Company.objects.filter(name=name).first()
        user = User.objects.filter(phone=phone).select_related("company").first()
        if company and user and self._is_matching_pair(company, user):
            self.stdout.write(
                self.style.SUCCESS("Kompaniya va administratori avval yaratilgan; o‘zgarish kiritilmadi.")
            )
            return
        if company:
            raise CommandError("Bu nomli kompaniya allaqachon mavjud.")
        if user:
            raise CommandError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")

        password = getpass("Administrator paroli: ")
        password_confirm = getpass("Parolni qayta kiriting: ")
        if password != password_confirm:
            raise CommandError("Parollar mos kelmadi.")

        try:
            with transaction.atomic():
                company = Company.objects.filter(name=name).first()
                user = User.objects.filter(phone=phone).select_related("company").first()
                if company and user and self._is_matching_pair(company, user):
                    already_exists = True
                elif company:
                    raise CommandError("Bu nomli kompaniya allaqachon mavjud.")
                elif user:
                    raise CommandError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")
                else:
                    company = Company(name=name)
                    company.full_clean()
                    company.save()

                    user = User(
                        phone=phone,
                        role=User.Role.COMPANY_ADMIN,
                        company=company,
                    )
                    validate_password(password, user=user)
                    user.full_clean(exclude=("password",))
                    user.set_password(password)
                    user.save()

                    AuditLog.objects.create(
                        actor=user,
                        company=company,
                        action="company.created",
                        entity_type="Company",
                        entity_id=str(company.pk),
                        after={
                            "name": company.name,
                            "initial_admin_id": user.pk,
                            "initial_admin_phone": user.phone,
                        },
                    )
                    already_exists = False
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        except IntegrityError as error:
            company = Company.objects.filter(name=name).first()
            user = User.objects.filter(phone=phone).select_related("company").first()
            if company and user and self._is_matching_pair(company, user):
                already_exists = True
            else:
                raise CommandError(
                    "Kompaniya yoki administrator yozuvi boshqa amal bilan to‘qnashdi."
                ) from error

        if already_exists:
            self.stdout.write(
                self.style.SUCCESS("Kompaniya va administratori avval yaratilgan; o‘zgarish kiritilmadi.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Kompaniya va administrator yaratildi: {company.name} ({user.phone})."
            )
        )

    @staticmethod
    def _is_matching_pair(company, user):
        return (
            user.role == User.Role.COMPANY_ADMIN
            and user.company_id == company.pk
        )
