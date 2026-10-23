from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.companies.models import Company
from apps.logistics.models import DriverProfile


class CreateStaffCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Sinov kompaniyasi")

    def run_command(self, *, phone="+998901234567", role="company_admin", company=None):
        call_command(
            "create_staff",
            "--phone",
            phone,
            "--role",
            role,
            "--company",
            str(company if company is not None else self.company.pk),
            stdout=StringIO(),
        )

    def test_creates_driver_profile_and_audit_without_printing_password(self):
        output = StringIO()
        with patch(
            "apps.accounts.management.commands.create_staff.getpass",
            side_effect=("Strong-Unique-Pass-927!", "Strong-Unique-Pass-927!"),
        ) as password_prompt:
            call_command(
                "create_staff",
                "--phone",
                "+998901234567",
                "--role",
                "driver",
                "--company",
                str(self.company.pk),
                stdout=output,
            )

        user = User.objects.get(phone="+998901234567")
        self.assertEqual(user.role, User.Role.DRIVER)
        self.assertEqual(user.company, self.company)
        self.assertTrue(user.check_password("Strong-Unique-Pass-927!"))
        self.assertTrue(DriverProfile.objects.filter(company=self.company, user=user).exists())
        self.assertTrue(AuditLog.objects.filter(
            company=self.company,
            entity_type="User",
            entity_id=str(user.pk),
            action="staff.created",
        ).exists())
        self.assertNotIn("Strong-Unique-Pass-927!", output.getvalue())
        self.assertEqual(password_prompt.call_count, 2)

    def test_creates_company_admin_without_driver_profile(self):
        with patch(
            "apps.accounts.management.commands.create_staff.getpass",
            side_effect=("Strong-Unique-Pass-927!", "Strong-Unique-Pass-927!"),
        ):
            self.run_command()

        user = User.objects.get(phone="+998901234567")
        self.assertEqual(user.role, User.Role.COMPANY_ADMIN)
        self.assertFalse(DriverProfile.objects.filter(user=user).exists())

    def test_rejects_invalid_phone_duplicate_phone_and_unknown_company(self):
        for phone, company, message in (
            ("901234567", self.company.pk, "Telefon"),
            ("+998901234567", 99999, "Kompaniya"),
        ):
            with self.subTest(phone=phone, company=company):
                with self.assertRaisesMessage(CommandError, message):
                    self.run_command(phone=phone, company=company)

        User.objects.create_user(
            phone="+998901234567",
            role=User.Role.COMPANY_ADMIN,
            company=self.company,
        )
        with self.assertRaisesMessage(CommandError, "allaqachon"):
            self.run_command()

    def test_rejects_password_mismatch_and_invalid_password(self):
        with patch(
            "apps.accounts.management.commands.create_staff.getpass",
            side_effect=("Strong-Unique-Pass-927!", "Different-Password-927!"),
        ):
            with self.assertRaisesMessage(CommandError, "mos kelmadi"):
                self.run_command()
        self.assertFalse(User.objects.filter(phone="+998901234567").exists())

        with patch(
            "apps.accounts.management.commands.create_staff.getpass",
            side_effect=("12345678", "12345678"),
        ):
            with self.assertRaises(CommandError):
                self.run_command()
        self.assertFalse(User.objects.filter(phone="+998901234567").exists())
