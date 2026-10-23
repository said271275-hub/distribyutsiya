import re
from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.companies.models import Company
from apps.logistics.models import DriverProfile


PHONE_PATTERN = re.compile(r"^\+998\d{9}$")
STAFF_ROLES = (User.Role.COMPANY_ADMIN, User.Role.DRIVER)


class Command(BaseCommand):
    help = "Kompaniya administratori yoki haydovchi akkauntini yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--phone", required=True)
        parser.add_argument("--role", required=True, choices=STAFF_ROLES)
        parser.add_argument("--company", required=True, help="Kompaniya nomi yoki ID raqami.")

    def handle(self, *args, **options):
        phone = options["phone"]
        if not PHONE_PATTERN.fullmatch(phone):
            raise CommandError("Telefon +998XXXXXXXXX shaklida bo‘lishi kerak.")
        if User.objects.filter(phone=phone).exists():
            raise CommandError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")

        company_arg = options["company"]
        company_query = (
            Company.objects.filter(pk=int(company_arg))
            if company_arg.isdecimal()
            else Company.objects.filter(name=company_arg)
        )
        companies = list(company_query[:2])
        if not companies:
            raise CommandError("Kompaniya topilmadi.")
        if len(companies) > 1:
            raise CommandError("Bu nomli bir nechta kompaniya bor; ID raqamini kiriting.")
        company = companies[0]

        password = getpass("Parol: ")
        password_confirm = getpass("Parolni qayta kiriting: ")
        if password != password_confirm:
            raise CommandError("Parollar mos kelmadi.")

        user = User(phone=phone, role=options["role"], company=company)
        try:
            validate_password(password, user=user)
            user.full_clean(exclude=("password",))
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        with transaction.atomic():
            user.set_password(password)
            user.save()
            if user.role == User.Role.DRIVER:
                DriverProfile.objects.create(company=company, user=user)
            AuditLog.objects.create(
                company=company,
                action="staff.created",
                entity_type="User",
                entity_id=str(user.pk),
                after={
                    "phone": user.phone,
                    "role": user.role,
                    "source": "create_staff management command",
                },
            )

        self.stdout.write(
            self.style.SUCCESS(f"Xodim yaratildi: {phone} ({user.get_role_display()}).")
        )
