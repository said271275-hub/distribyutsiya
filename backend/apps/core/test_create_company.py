from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.companies.models import Company


class CreateCompanyCommandTests(TestCase):
    def test_creates_company_and_first_admin_with_hidden_password(self):
        output = StringIO()
        with patch(
            "apps.core.management.commands.create_company.getpass",
            side_effect=("Unique-Safe-Password-839!", "Unique-Safe-Password-839!"),
        ) as hidden_prompt:
            call_command(
                "create_company",
                "--name",
                "Pepsi",
                "--admin-phone",
                "+998900123456",
                stdout=output,
            )

        company = Company.objects.get(name="Pepsi")
        admin = User.objects.get(phone="+998900123456")
        self.assertEqual(admin.role, User.Role.COMPANY_ADMIN)
        self.assertEqual(admin.company, company)
        self.assertTrue(admin.check_password("Unique-Safe-Password-839!"))
        self.assertNotIn("Unique-Safe-Password-839!", output.getvalue())
        self.assertEqual(hidden_prompt.call_count, 2)
        self.assertTrue(
            AuditLog.objects.filter(
                company=company,
                actor=admin,
                action="company.created",
                entity_type="Company",
            ).exists()
        )

    def test_repeated_command_does_not_create_duplicates_or_prompt_again(self):
        with patch(
            "apps.core.management.commands.create_company.getpass",
            side_effect=("Unique-Safe-Password-839!", "Unique-Safe-Password-839!"),
        ):
            call_command(
                "create_company",
                "--name",
                "Pepsi",
                "--admin-phone",
                "+998900123456",
                stdout=StringIO(),
            )

        repeated_output = StringIO()
        with patch(
            "apps.core.management.commands.create_company.getpass",
            side_effect=AssertionError("Parol so‘ralmasligi kerak."),
        ):
            call_command(
                "create_company",
                "--name",
                "Pepsi",
                "--admin-phone",
                "+998900123456",
                stdout=repeated_output,
            )

        self.assertEqual(Company.objects.filter(name="Pepsi").count(), 1)
        self.assertEqual(
            User.objects.filter(
                phone="+998900123456",
                role=User.Role.COMPANY_ADMIN,
            ).count(),
            1,
        )
        self.assertIn("avval yaratilgan", repeated_output.getvalue())

    def test_mismatched_passwords_do_not_create_records(self):
        with (
            patch(
                "apps.core.management.commands.create_company.getpass",
                side_effect=("Unique-Safe-Password-839!", "Another-Safe-Password-839!"),
            ),
            self.assertRaisesMessage(CommandError, "Parollar mos kelmadi."),
        ):
            call_command(
                "create_company",
                "--name",
                "Pepsi",
                "--admin-phone",
                "+998900123456",
                stdout=StringIO(),
            )

        self.assertFalse(Company.objects.exists())
        self.assertFalse(User.objects.exists())

    def test_existing_name_or_phone_is_rejected_without_writes(self):
        company = Company.objects.create(name="Pepsi")
        with patch(
            "apps.core.management.commands.create_company.getpass",
            side_effect=AssertionError("Parol so‘ralmasligi kerak."),
        ):
            with self.assertRaisesMessage(CommandError, "Bu nomli kompaniya allaqachon mavjud."):
                call_command(
                    "create_company",
                    "--name",
                    "Pepsi",
                    "--admin-phone",
                    "+998900123456",
                    stdout=StringIO(),
                )

        User.objects.create_user(
            phone="+998900123456",
            password="Unique-Safe-Password-839!",
            role=User.Role.SHOP_OWNER,
        )
        with self.assertRaisesMessage(CommandError, "Bu telefon raqami allaqachon ro‘yxatdan o‘tgan."):
            call_command(
                "create_company",
                "--name",
                "Another company",
                "--admin-phone",
                "+998900123456",
                stdout=StringIO(),
            )

        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(company.name, "Pepsi")
