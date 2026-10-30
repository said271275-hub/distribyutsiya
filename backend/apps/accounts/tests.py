import os
import secrets
import subprocess
import sys
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.accounts.models import (
    DeletionRequest,
    LoginAttempt,
    PhoneOTP,
    User,
)
from apps.accounts.services import normalize_uz_phone
from apps.accounts.sms import (
    DevOtpProvider,
    EskizSmsClient,
    SmsProviderError,
    get_otp_provider,
)
from apps.audit.models import AuditLog
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.core.permissions import (
    CompanyAdminPermission,
    CompanyScopedQuerysetMixin,
    DriverPermission,
    DriverTripScopedQuerysetMixin,
    ShopOwnerPermission,
    ShopOwnerScopedQuerysetMixin,
)
from apps.core.filters import CompanyTenantFilterBackend
from apps.logistics.models import DriverProfile, Trip, TripStop, Vehicle
from apps.orders.models import Order
from apps.payments.models import ShopBalance

PASSWORD = "Sirdaryo!StrongPassword938"
DEV_TEST_OTP_CODE = f"{secrets.randbelow(1_000_000):06d}"


class AdminUzbekLabelsTests(SimpleTestCase):
    def test_registered_model_and_field_labels_are_uzbek(self):
        self.assertEqual(str(User._meta.verbose_name), "Foydalanuvchi")
        self.assertEqual(str(User._meta.verbose_name_plural), "Foydalanuvchilar")
        self.assertEqual(str(User._meta.get_field("phone").verbose_name), "Telefon raqami")
        self.assertEqual(str(User._meta.get_field("company").verbose_name), "Kompaniya")
        self.assertEqual(str(User._meta.get_field("is_active").verbose_name), "Faol")
        self.assertEqual(str(DeletionRequest._meta.verbose_name_plural), "Akkauntni o‘chirish so‘rovlari")
        self.assertEqual(str(AuditLog._meta.verbose_name_plural), "Harakatlar jurnali")

    def test_admin_branding_and_user_field_groups_are_uzbek(self):
        from django.contrib import admin
        from apps.accounts.admin import UserAdmin

        self.assertEqual(str(admin.site.site_header), "Tarqatuv boshqaruv tizimi")
        self.assertEqual(str(admin.site.index_title), "Boshqaruv bo‘limlari")
        self.assertEqual(
            [str(title) for title, _options in UserAdmin.fieldsets],
            [
                "Kirish ma’lumotlari",
                "Kompaniya va vazifa",
                "Hisob holati",
                "Boshqaruv huquqlari",
                "Faollik va vaqt",
            ],
        )


class ProductionSettingsTests(SimpleTestCase):
    def production_environment(self):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SECRET_KEY="test-only-secret-key-" + ("x" * 60),
            DJANGO_ENV="production",
            DJANGO_DEBUG="False",
            DJANGO_ALLOWED_HOSTS="example.test",
            DJANGO_CSRF_TRUSTED_ORIGINS="https://example.test",
            DJANGO_CORS_ALLOWED_ORIGINS="",
            DJANGO_SECURE_SSL_REDIRECT="True",
            DJANGO_SECURE_COOKIES="True",
            AUTH_COOKIE_SECURE="True",
            DJANGO_SECURE_HSTS_SECONDS="31536000",
            DEV_OTP_ENABLED="False",
            DEV_STAFF_PASSWORD="",
            OTP_PROVIDER="apps.accounts.sms.EskizOtpProvider",
            ESKIZ_EMAIL="test@example.test",
            ESKIZ_PASSWORD="test-only-password",
            ESKIZ_FROM="TEST",
            POSTGRES_DB="test_db",
            POSTGRES_USER="test_user",
            POSTGRES_PASSWORD="test-only-password",
            POSTGRES_HOST="127.0.0.1",
        )
        return environment

    def load_settings(self, environment):
        return subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_settings_load_with_secure_values(self):
        environment = self.production_environment()
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from config.settings import (AUTH_COOKIE_HTTPONLY, AUTH_COOKIE_SECURE, "
                "DEBUG, SECURE_SSL_REDIRECT, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SECURE); "
                "assert not DEBUG and SECURE_SSL_REDIRECT and AUTH_COOKIE_SECURE "
                "and SESSION_COOKIE_SECURE and AUTH_COOKIE_HTTPONLY and SESSION_COOKIE_HTTPONLY",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dev_otp_is_rejected_during_production_settings_load(self):
        environment = self.production_environment()
        environment["DEV_OTP_ENABLED"] = "True"
        environment["DEV_OTP_CODE"] = DEV_TEST_OTP_CODE
        result = self.load_settings(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("DEV_OTP_ENABLED", result.stderr)

    def test_dev_staff_password_is_rejected_in_production(self):
        environment = self.production_environment()
        environment["DEV_STAFF_PASSWORD"] = "temporary-test-password"
        result = self.load_settings(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEV_STAFF_PASSWORD", result.stderr)

    def test_production_requires_eskiz_configuration(self):
        environment = self.production_environment()
        for key in ("ESKIZ_EMAIL", "ESKIZ_PASSWORD", "ESKIZ_FROM"):
            environment.pop(key, None)
        result = self.load_settings(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ESKIZ_EMAIL", result.stderr)

    def test_production_settings_reject_insecure_transport(self):
        environment = self.production_environment()
        environment["DJANGO_SECURE_SSL_REDIRECT"] = "False"
        result = self.load_settings(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTPS yo‘naltirishi", result.stderr)

    def test_production_settings_reject_remote_database_host(self):
        environment = self.production_environment()
        environment["POSTGRES_HOST"] = "database.example.test"
        result = self.load_settings(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("faqat mahalliy manzilda", result.stderr)

    def test_production_environment_rejects_debug_mode(self):
        environment = self.production_environment()
        environment["DJANGO_DEBUG"] = "True"
        result = self.load_settings(environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_DEBUG=False", result.stderr)


class OrderSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    company_id = serializers.IntegerField()
    shop_id = serializers.IntegerField()


class TripSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    company_id = serializers.IntegerField()


class CompanySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ShopOrderDetailView(ShopOwnerScopedQuerysetMixin, generics.RetrieveAPIView):
    authentication_classes = ()
    permission_classes = (IsAuthenticated, ShopOwnerPermission)
    queryset = Order.objects.all()
    serializer_class = OrderSummarySerializer


class CompanyOrderDetailView(CompanyScopedQuerysetMixin, generics.RetrieveAPIView):
    authentication_classes = ()
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    queryset = Order.objects.all()
    serializer_class = OrderSummarySerializer


class AutomaticTenantOrderDetailView(generics.RetrieveAPIView):
    authentication_classes = ()
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    filter_backends = (CompanyTenantFilterBackend,)
    queryset = Order.objects.all()
    serializer_class = OrderSummarySerializer


class AutomaticTenantCompanyDetailView(generics.RetrieveAPIView):
    authentication_classes = ()
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    filter_backends = (CompanyTenantFilterBackend,)
    queryset = Company.objects.all()
    serializer_class = CompanySummarySerializer


class DriverTripDetailView(DriverTripScopedQuerysetMixin, generics.RetrieveAPIView):
    authentication_classes = ()
    permission_classes = (IsAuthenticated, DriverPermission)
    queryset = Trip.objects.all()
    serializer_class = TripSummarySerializer


class AuthFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company_a = Company.objects.create(name="Kompaniya A")
        cls.company_b = Company.objects.create(name="Kompaniya B")
        cls.shop_user = User.objects.create_user(
            phone="+998901234567",
            password=PASSWORD,
            role=User.Role.SHOP_OWNER,
        )
        cls.shop = Shop.objects.create(
            owner=cls.shop_user,
            name="A do‘kon",
            phone_primary="+998909876543",
            address="Guliston",
            district="Guliston",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        CompanyShopLink.objects.create(company=cls.company_a, shop=cls.shop)
        cls.staff_user = User.objects.create_user(
            phone="+998901111111",
            password=PASSWORD,
            company=cls.company_a,
            role=User.Role.COMPANY_ADMIN,
        )
        cls.other_shop_user = User.objects.create_user(
            phone="+998902222222",
            password=PASSWORD,
            role=User.Role.SHOP_OWNER,
        )
        cls.other_shop = Shop.objects.create(
            owner=cls.other_shop_user,
            name="B do‘kon",
            phone_primary="+998903333333",
            address="Yangiyer",
            district="Yangiyer",
            latitude=Decimal("40.850000"),
            longitude=Decimal("68.670000"),
        )
        CompanyShopLink.objects.create(company=cls.company_b, shop=cls.other_shop)
        cls.order_a = Order.objects.create(
            company=cls.company_a,
            shop=cls.shop,
            delivery_date="2026-10-15",
        )
        cls.order_b = Order.objects.create(
            company=cls.company_b,
            shop=cls.other_shop,
            delivery_date="2026-10-15",
        )
        cls.driver_user = User.objects.create_user(
            phone="+998904444444",
            password=PASSWORD,
            company=cls.company_a,
            role=User.Role.DRIVER,
        )
        cls.driver_profile = DriverProfile.objects.create(
            company=cls.company_a, user=cls.driver_user
        )
        cls.vehicle = Vehicle.objects.create(
            company=cls.company_a,
            name="A transport",
            plate_number="01A111AA",
            capacity=Decimal("1000.00"),
        )
        cls.trip = Trip.objects.create(
            company=cls.company_a,
            date="2026-10-15",
            vehicle=cls.vehicle,
            driver=cls.driver_profile,
        )
        cls.stop = TripStop.objects.create(
            company=cls.company_a, trip=cls.trip, shop=cls.shop, sequence=1
        )
        cls.other_trip = Trip.objects.create(
            company=cls.company_a,
            date="2026-10-16",
            vehicle=cls.vehicle,
            driver=cls.driver_profile,
        )

    def setUp(self):
        self.client = APIClient()

    def login(self, *, staff=False, phone=None):
        phone = phone or (self.staff_user.phone if staff else self.shop_user.phone)
        path = "/api/auth/staff/login/" if staff else "/api/auth/login/"
        return self.client.post(
            path,
            {"phone": phone, "password": PASSWORD},
            format="json",
        )

    def request_sms_code(self, path, payload):
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            return self.client.post(path, payload, format="json")

    def bearer_client(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return self.client

    def test_shopkeeper_and_staff_have_separate_login_endpoints(self):
        shop_login = self.login()
        self.assertEqual(shop_login.status_code, 200)
        self.assertEqual(shop_login.data["user"]["role"], User.Role.SHOP_OWNER)
        cookie = shop_login.cookies["distribyutsiya_refresh"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

        self.client.credentials()
        self.assertEqual(self.login(staff=True).status_code, 200)
        self.assertEqual(self.login(staff=True, phone=self.shop_user.phone).status_code, 401)
        self.assertEqual(self.login(phone=self.staff_user.phone).status_code, 401)

    def test_driver_can_login_through_staff_endpoint(self):
        response = self.login(staff=True, phone=self.driver_user.phone)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["user"]["id"], self.driver_user.pk)
        self.assertEqual(response.data["user"]["role"], User.Role.DRIVER)
        self.assertEqual(response.data["user"]["company_id"], self.company_a.pk)

    def test_registration_uses_one_time_sms_code_and_phone_is_unique(self):
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            requested = self.client.post(
                "/api/auth/register/otp/",
                {"phone": "90 555 66 77"},
                format="json",
            )
        self.assertEqual(requested.status_code, 202)
        self.assertNotIn(DEV_TEST_OTP_CODE, str(requested.data))

        registered = self.client.post(
            "/api/auth/register/",
            {
                "phone": "+998905556677",
                "code": DEV_TEST_OTP_CODE,
                "password": PASSWORD,
                "role": User.Role.DRIVER,
                "company_id": self.company_a.pk,
            },
            format="json",
        )
        self.assertEqual(registered.status_code, 201)
        user = User.objects.get(phone="+998905556677")
        self.assertEqual(user.role, User.Role.SHOP_OWNER)
        self.assertTrue(user.check_password(PASSWORD))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(phone=user.phone, role=User.Role.SHOP_OWNER)

        duplicate = self.client.post(
            "/api/auth/register/otp/",
            {"phone": "+998905556677"},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_wrong_otp_attempts_are_limited_and_persisted(self):
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            self.client.post(
                "/api/auth/register/otp/",
                {"phone": "+998905551010"},
                format="json",
            )
        for _ in range(5):
            response = self.client.post(
                "/api/auth/register/",
                {"phone": "+998905551010", "code": "000000", "password": PASSWORD},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
        otp = PhoneOTP.objects.get(phone="+998905551010")
        self.assertEqual(otp.failed_attempts, 5)
        self.assertIsNotNone(otp.consumed_at)

    def test_expired_registration_otp_is_rejected(self):
        phone = "+998905551013"
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            requested = self.client.post(
                "/api/auth/register/otp/",
                {"phone": phone},
                format="json",
            )
            self.assertEqual(requested.status_code, 202)
            PhoneOTP.objects.filter(phone=phone).update(
                expires_at=timezone.now() - timedelta(seconds=1)
            )
            response = self.client.post(
                "/api/auth/register/",
                {"phone": phone, "code": DEV_TEST_OTP_CODE, "password": PASSWORD},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("muddati", str(response.data).lower())

    def test_sms_send_rate_limit_is_three_codes_per_phone(self):
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            responses = [
                self.client.post(
                    "/api/auth/register/otp/",
                    {"phone": "+998905551011"},
                    format="json",
                )
                for _ in range(4)
            ]
        self.assertEqual([response.status_code for response in responses], [202, 202, 202, 400])
        self.assertEqual(PhoneOTP.objects.filter(phone="+998905551011").count(), 3)

    def test_dev_otp_provider_uses_configured_code_without_sending_sms(self):
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            provider = get_otp_provider()
            self.assertIsInstance(provider, DevOtpProvider)
            self.assertEqual(provider.generate_code(), DEV_TEST_OTP_CODE)
            self.assertIsNone(provider.send("+998901234567", DEV_TEST_OTP_CODE))

        with override_settings(DEV_OTP_ENABLED=False):
            with self.assertRaises(ImproperlyConfigured):
                DevOtpProvider().generate_code()

        with override_settings(OTP_PROVIDER=""):
            with self.assertRaises(ImproperlyConfigured):
                get_otp_provider()

    def test_login_uses_password_without_sending_sms(self):
        response = self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(PhoneOTP.objects.filter(phone=self.shop_user.phone).exists())
        self.assertFalse(response.data["user"]["must_change_password"])

        invalid = self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": "incorrect"},
            format="json",
        )
        unknown = self.client.post(
            "/api/auth/login/",
            {"phone": "+998909999999", "password": "incorrect"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(invalid.data["detail"], unknown.data["detail"])
        self.assertEqual(invalid.data["detail"], "Telefon yoki parol noto‘g‘ri.")

    def test_password_reset_revokes_existing_access_and_refresh_tokens(self):
        signed_in = self.login()
        self.assertEqual(signed_in.status_code, 200)
        old_access = signed_in.data["access"]
        old_refresh = signed_in.cookies["distribyutsiya_refresh"].value
        self.client.cookies["distribyutsiya_refresh"] = old_refresh

        requested = self.request_sms_code(
            "/api/auth/password/reset/otp/", {"phone": self.shop_user.phone}
        )
        self.assertEqual(requested.status_code, 202)
        otp = PhoneOTP.objects.get(
            phone=self.shop_user.phone,
            purpose=PhoneOTP.Purpose.PASSWORD_RESET,
        )
        self.assertNotEqual(otp.code_hash, DEV_TEST_OTP_CODE)
        new_password = "New!SirdaryoPassword729"
        reset = self.client.post(
            "/api/auth/password/reset/",
            {
                "phone": self.shop_user.phone,
                "code": DEV_TEST_OTP_CODE,
                "password": new_password,
                "password_confirm": new_password,
            },
            format="json",
        )
        self.assertEqual(reset.status_code, 200, reset.data)
        self.assertNotIn(new_password, str(reset.data))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

        updated_user = User.objects.get(pk=self.shop_user.pk)
        self.assertTrue(updated_user.check_password(new_password))
        self.assertFalse(updated_user.must_change_password)
        relogin = self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": new_password},
            format="json",
        )
        self.assertEqual(relogin.status_code, 200, relogin.data)

    def test_password_reset_rejects_bad_codes_and_weak_passwords(self):
        self.request_sms_code(
            "/api/auth/password/reset/otp/", {"phone": self.shop_user.phone}
        )
        rejected_code = self.client.post(
            "/api/auth/password/reset/",
            {
                "phone": self.shop_user.phone,
                "code": "000000" if DEV_TEST_OTP_CODE != "000000" else "000001",
                "password": "New!SirdaryoPassword729",
                "password_confirm": "New!SirdaryoPassword729",
            },
            format="json",
        )
        self.assertEqual(rejected_code.status_code, 400)
        for password in ("12345678", "123456789", "short"):
            rejected_password = self.client.post(
                "/api/auth/password/reset/",
                {
                    "phone": self.shop_user.phone,
                    "code": DEV_TEST_OTP_CODE,
                    "password": password,
                    "password_confirm": password,
                },
                format="json",
            )
            self.assertEqual(rejected_password.status_code, 400, password)
        self.assertTrue(self.shop_user.check_password(PASSWORD))

    def test_registration_requires_a_valid_sms_code_before_creating_account(self):
        self.request_sms_code(
            "/api/auth/register/otp/", {"phone": "+998905558888"}
        )
        invalid = self.client.post(
            "/api/auth/register/",
            {
                "phone": "+998905558888",
                "code": "000000" if DEV_TEST_OTP_CODE != "000000" else "000001",
                "password": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(User.objects.filter(phone="+998905558888").exists())

    def test_first_staff_login_requires_password_change_and_rotates_tokens(self):
        staff = User.objects.create_user(
            phone="+998905557777",
            password=PASSWORD,
            company=self.company_a,
            role=User.Role.COMPANY_ADMIN,
            must_change_password=True,
        )
        login = self.login(staff=True, phone=staff.phone)
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])
        self.bearer_client(login.data["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        denied = self.client.get("/api/auth/me/deletion/")
        self.assertEqual(denied.status_code, 401)
        changed = self.client.post(
            "/api/auth/password/change/",
            {
                "current_password": PASSWORD,
                "password": "Changed!SirdaryoPassword729",
                "password_confirm": "Changed!SirdaryoPassword729",
            },
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertFalse(changed.data["user"]["must_change_password"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.bearer_client(changed.data["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        staff.refresh_from_db()
        self.assertTrue(staff.check_password("Changed!SirdaryoPassword729"))
        self.assertFalse(staff.must_change_password)

    def test_phone_change_needs_sms_and_invalidates_old_tokens(self):
        login = self.login()
        self.bearer_client(login.data["access"])
        requested = self.request_sms_code(
            "/api/auth/phone/change/otp/", {"phone": "+998905559999"}
        )
        self.assertEqual(requested.status_code, 202, requested.data)
        changed = self.client.post(
            "/api/auth/phone/change/",
            {"phone": "+998905559999", "code": DEV_TEST_OTP_CODE},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data["user"]["phone"], "+998905559999")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_eskiz_refreshes_expiring_token_using_official_refresh_route(self):
        client = EskizSmsClient()
        client._token = "old-token"
        client._token_email = ""
        client._token_renew_at = 0
        with override_settings(ESKIZ_EMAIL=""):
            with patch.object(
                client,
                "_post",
                return_value={"data": {"token": "renewed-token"}},
            ) as post:
                token = client._get_token()

        self.assertEqual(token, "renewed-token")
        post.assert_called_once_with("/auth/refresh", None, "old-token")

    def test_eskiz_relogs_in_when_expired_refresh_token_is_rejected(self):
        client = EskizSmsClient()
        client._token = "expired-token"
        client._token_email = ""
        client._token_renew_at = 0
        with override_settings(ESKIZ_EMAIL=""):
            with patch.object(
                client,
                "_post",
                side_effect=[
                    SmsProviderError("http_error", 401),
                    {"data": {"token": "new-token"}},
                ],
            ) as post:
                token = client._get_token()

        self.assertEqual(token, "new-token")
        self.assertEqual(post.call_args_list[0].args[0], "/auth/refresh")
        self.assertEqual(post.call_args_list[1].args[0], "/auth/login")

    def test_otp_sms_failure_log_contains_only_phone_suffix(self):
        provider = Mock()
        provider.generate_code.return_value = DEV_TEST_OTP_CODE
        provider.send.side_effect = SmsProviderError("network_error")
        with override_settings(OTP_PROVIDER="apps.accounts.sms.EskizOtpProvider"):
            with patch(
                "apps.accounts.sms.get_otp_provider",
                return_value=provider,
            ):
                with self.assertLogs("apps.accounts.services", level="WARNING") as captured:
                    response = self.client.post(
                        "/api/auth/register/otp/",
                        {"phone": "+998905551212"},
                        format="json",
                    )

        self.assertEqual(response.status_code, 400)
        text = "\n".join(captured.output)
        self.assertIn("1212", text)
        self.assertNotIn("+998905551212", text)
        self.assertNotIn(DEV_TEST_OTP_CODE, text)

    def test_five_failed_logins_create_a_temporary_block(self):
        for index in range(5):
            response = self.client.post(
                "/api/auth/login/",
                {"phone": self.shop_user.phone, "password": f"wrong-{index}"},
                format="json",
            )
            self.assertEqual(response.status_code, 401)
        attempt = LoginAttempt.objects.get(
            phone=self.shop_user.phone, scope="phone"
        )
        self.assertEqual(attempt.failures, 5)
        self.assertGreater(attempt.blocked_until, timezone.now())
        self.assertEqual(self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
            format="json",
        ).data["detail"], "Telefon yoki parol noto‘g‘ri.")

    def test_login_attempts_are_limited_by_phone_and_ip(self):
        for index in range(5):
            self.client.post(
                "/api/auth/login/",
                {"phone": f"+99890{index:07d}", "password": "wrong"},
                format="json",
                REMOTE_ADDR="192.0.2.10",
            )
        ip_attempt = LoginAttempt.objects.get(phone="__ip__", ip_address="192.0.2.10", scope="ip")
        self.assertEqual(ip_attempt.failures, 5)
        self.assertGreater(ip_attempt.blocked_until, timezone.now())
        locked = self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
            format="json",
            REMOTE_ADDR="192.0.2.10",
        )
        self.assertEqual(locked.status_code, 401)
        self.assertEqual(locked.data["detail"], "Telefon yoki parol noto‘g‘ri.")

    def test_login_block_expires_after_the_configured_window(self):
        attempt = LoginAttempt.objects.create(
            phone=self.shop_user.phone,
            ip_address="0.0.0.0",
            scope="phone",
            failures=5,
            blocked_until=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(LoginAttempt.objects.filter(pk=attempt.pk).exists())

    def test_login_success_and_failure_are_written_to_audit_log(self):
        failed = self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(failed.status_code, 401)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.shop_user,
                action="shop_login_failed",
                entity_type="Login",
            ).exists()
        )

        succeeded = self.login()
        self.assertEqual(succeeded.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.shop_user,
                action="shop_login_succeeded",
                entity_type="Login",
            ).exists()
        )

    def test_refresh_rotates_http_only_cookie_and_logout_revokes_refresh(self):
        login = self.login()
        self.assertEqual(login.status_code, 200)
        first_refresh = login.cookies["distribyutsiya_refresh"].value
        refreshed = self.client.post("/api/auth/refresh/")
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("access", refreshed.data)
        second_refresh = refreshed.cookies["distribyutsiya_refresh"].value
        self.assertNotEqual(first_refresh, second_refresh)

        logout = self.client.post("/api/auth/logout/")
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_shopkeeper_cannot_delete_account_with_open_order_or_debt(self):
        login = self.login()
        self.bearer_client(login.data["access"])
        blocked_by_order = self.client.post(
            "/api/auth/me/deletion/",
            {"reason": "not_needed", "password": PASSWORD, "code": DEV_TEST_OTP_CODE},
            format="json",
        )
        self.assertEqual(blocked_by_order.status_code, 400)
        self.assertIn("Ochiq buyurtmalar", str(blocked_by_order.data))

        self.order_a.status = Order.Status.DELIVERED
        self.order_a.save(update_fields=("status", "updated_at"))
        ShopBalance.objects.create(
            company=self.company_a,
            shop=self.shop,
            current_balance=Decimal("1000.00"),
        )
        blocked_by_debt = self.client.post(
            "/api/auth/me/deletion/",
            {"reason": "not_needed", "password": PASSWORD, "code": DEV_TEST_OTP_CODE},
            format="json",
        )
        self.assertEqual(blocked_by_debt.status_code, 400)
        self.assertIn("qarz", str(blocked_by_debt.data).lower())

    def test_account_deletion_requires_the_current_password_and_reason(self):
        self.order_a.status = Order.Status.DELIVERED
        self.order_a.save(update_fields=("status", "updated_at"))
        login = self.login()
        self.bearer_client(login.data["access"])

        self.request_sms_code("/api/auth/me/deletion/otp/", {})
        wrong_password = self.client.post(
            "/api/auth/me/deletion/",
            {"reason": "not_needed", "password": "wrong-password", "code": DEV_TEST_OTP_CODE},
            format="json",
        )
        self.assertEqual(wrong_password.status_code, 400)
        self.assertFalse(
            self.shop_user.deletion_requests.filter(
                status=DeletionRequest.Status.PENDING
            ).exists()
        )

        missing_reason = self.client.post(
            "/api/auth/me/deletion/",
            {"password": PASSWORD, "code": DEV_TEST_OTP_CODE},
            format="json",
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertFalse(
            self.shop_user.deletion_requests.filter(
                status=DeletionRequest.Status.PENDING
            ).exists()
        )

    def test_account_deletion_can_be_restored_within_grace_period(self):
        self.order_a.status = Order.Status.DELIVERED
        self.order_a.save(update_fields=("status", "updated_at"))
        login = self.login()
        old_access = login.data["access"]
        old_refresh = login.cookies["distribyutsiya_refresh"].value
        self.bearer_client(login.data["access"])
        self.request_sms_code("/api/auth/me/deletion/otp/", {})
        requested = self.client.post(
            "/api/auth/me/deletion/",
            {
                "reason": "other",
                "reason_other": "Boshqa sabab",
                "password": PASSWORD,
                "code": DEV_TEST_OTP_CODE,
            },
            format="json",
        )
        self.assertEqual(requested.status_code, 202)
        self.shop_user.refresh_from_db()
        self.assertTrue(self.shop_user.is_blocked)
        self.assertEqual(
            self.shop_user.deletion_requests.get().scheduled_for,
            self.shop_user.deletion_requests.get().requested_at + timedelta(days=30),
        )
        blocked = self.client.get("/api/auth/me/")
        self.assertEqual(blocked.status_code, 401)

        self.client.credentials()
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            restore_code = self.client.post(
                "/api/auth/restore/otp/",
                {"phone": self.shop_user.phone, "password": PASSWORD},
                format="json",
            )
            self.assertEqual(restore_code.status_code, 202, restore_code.data)
            restored = self.client.post(
                "/api/auth/restore/",
                {
                    "phone": self.shop_user.phone,
                    "password": PASSWORD,
                    "code": DEV_TEST_OTP_CODE,
                },
                format="json",
            )
        self.assertEqual(restored.status_code, 200)
        self.shop_user.refresh_from_db()
        self.assertFalse(self.shop_user.is_blocked)
        self.assertTrue(self.shop_user.is_active)
        self.assertEqual(
            self.shop_user.deletion_requests.get().status,
            DeletionRequest.Status.CANCELLED,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.client.credentials()
        self.client.cookies["distribyutsiya_refresh"] = old_refresh
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_due_deletion_anonymizes_shop_and_user_but_preserves_orders(self):
        self.order_a.status = Order.Status.DELIVERED
        self.order_a.save(update_fields=("status", "updated_at"))
        deletion = DeletionRequest.objects.create(
            user=self.shop_user, reason=DeletionRequest.Reason.STORE_CLOSED
        )
        DeletionRequest.objects.filter(pk=deletion.pk).update(
            scheduled_for=timezone.now() - timedelta(seconds=1)
        )
        call_command("process_account_deletions", stdout=StringIO())

        self.shop_user.refresh_from_db()
        self.shop.refresh_from_db()
        deletion.refresh_from_db()
        self.order_a.refresh_from_db()
        self.assertTrue(self.shop_user.is_deleted)
        self.assertEqual(self.shop_user.phone, f"deleted-user-{self.shop_user.pk}")
        self.assertEqual(self.shop.name, f"O‘chirilgan do‘kon #{self.shop.pk}")
        self.assertEqual(self.shop.status, Shop.Status.ARCHIVED)
        self.assertEqual(deletion.status, DeletionRequest.Status.COMPLETED)
        self.assertEqual(self.order_a.shop_id, self.shop.pk)
        self.assertTrue(Order.objects.filter(pk=self.order_a.pk).exists())

    def test_shop_owner_idor_company_isolation_and_driver_trip_scoping(self):
        factory = APIRequestFactory()

        shop_request = factory.get(f"/api/test/orders/{self.order_b.pk}/")
        force_authenticate(shop_request, user=self.shop_user)
        response = ShopOrderDetailView.as_view()(shop_request, pk=self.order_b.pk)
        self.assertEqual(response.status_code, 404)

        company_request = factory.get(f"/api/test/orders/{self.order_b.pk}/")
        force_authenticate(company_request, user=self.staff_user)
        response = CompanyOrderDetailView.as_view()(
            company_request, pk=self.order_b.pk
        )
        self.assertEqual(response.status_code, 404)

        company_page_request = factory.get(f"/api/test/orders/{self.order_a.pk}/")
        force_authenticate(company_page_request, user=self.shop_user)
        response = CompanyOrderDetailView.as_view()(
            company_page_request, pk=self.order_a.pk
        )
        self.assertEqual(response.status_code, 403)

        shop_page_request = factory.get(f"/api/test/orders/{self.order_a.pk}/")
        force_authenticate(shop_page_request, user=self.staff_user)
        response = ShopOrderDetailView.as_view()(
            shop_page_request, pk=self.order_a.pk
        )
        self.assertEqual(response.status_code, 403)

        automatic_request = factory.get(f"/api/test/orders/{self.order_b.pk}/")
        force_authenticate(automatic_request, user=self.staff_user)
        response = AutomaticTenantOrderDetailView.as_view()(
            automatic_request, pk=self.order_b.pk
        )
        self.assertEqual(response.status_code, 404)

        company_request = factory.get(f"/api/test/companies/{self.company_b.pk}/")
        force_authenticate(company_request, user=self.staff_user)
        response = AutomaticTenantCompanyDetailView.as_view()(
            company_request, pk=self.company_b.pk
        )
        self.assertEqual(response.status_code, 404)

        another_driver = User.objects.create_user(
            phone="+998905555555",
            password=PASSWORD,
            company=self.company_a,
            role=User.Role.DRIVER,
        )
        another_profile = DriverProfile.objects.create(
            company=self.company_a, user=another_driver
        )
        other_trip = Trip.objects.create(
            company=self.company_a,
            date="2026-10-16",
            vehicle=self.vehicle,
            driver=another_profile,
        )
        other_trip_request = factory.get(f"/api/test/trips/{other_trip.pk}/")
        force_authenticate(other_trip_request, user=self.driver_user)
        response = DriverTripDetailView.as_view()(
            other_trip_request, pk=other_trip.pk
        )
        self.assertEqual(response.status_code, 404)

    def test_company_admin_tenant_filter_limits_company_shop_links(self):
        request = APIRequestFactory().get("/api/v1/companies/shops/")
        request.user = self.staff_user

        links = CompanyTenantFilterBackend().filter_queryset(
            request, CompanyShopLink.objects.all(), view=None
        )

        self.assertEqual(
            list(links.values_list("company_id", flat=True)), [self.company_a.pk]
        )

    def test_company_admin_permission_is_limited_to_company_staff(self):
        permission = CompanyAdminPermission()
        factory = APIRequestFactory()

        for user in (self.staff_user, User.objects.create_superuser(
            phone="+998906666666", password=PASSWORD
        )):
            request = factory.post("/api/v1/payments/")
            request.user = user
            self.assertTrue(permission.has_permission(request, None))

        for user in (self.shop_user, self.driver_user):
            request = factory.post("/api/v1/payments/")
            request.user = user
            self.assertFalse(permission.has_permission(request, None))

    def test_role_and_company_changes_are_audited(self):
        self.driver_user.role = User.Role.COMPANY_ADMIN
        self.driver_user.save(update_fields=("role",))
        event = AuditLog.objects.get(
            action="user_role_or_company_changed",
            entity_id=str(self.driver_user.pk),
        )
        self.assertEqual(event.before["role"], User.Role.DRIVER)
        self.assertEqual(event.after["role"], User.Role.COMPANY_ADMIN)

    def test_phone_normalization_rejects_non_uzbek_numbers(self):
        self.assertEqual(normalize_uz_phone("90 123 45 67"), "+998901234567")
        with self.assertRaises(DRFValidationError):
            normalize_uz_phone("+12025550123")

    def test_auth_post_requires_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        denied = client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
        csrf = client.get("/api/auth/csrf/")
        with override_settings(
            OTP_PROVIDER="apps.accounts.sms.DevOtpProvider",
            DEV_OTP_ENABLED=True,
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        ):
            allowed = client.post(
                "/api/auth/login/",
                {"phone": self.shop_user.phone, "password": PASSWORD},
                format="json",
                HTTP_X_CSRFTOKEN=csrf.data["csrfToken"],
            )
        self.assertEqual(allowed.status_code, 200)

    def test_django_admin_can_create_staff_users(self):
        superuser = User.objects.create_superuser(
            phone="+998907777777", password=PASSWORD
        )
        self.client.force_login(superuser)
        form = self.client.get("/admin/accounts/user/add/")
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, 'name="phone"')
        response = self.client.post(
            "/admin/accounts/user/add/",
            {
                "phone": "+998908888888",
                "role": User.Role.COMPANY_ADMIN,
                "company": str(self.company_a.pk),
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        staff_user = User.objects.get(phone="+998908888888")
        self.assertEqual(staff_user.role, User.Role.COMPANY_ADMIN)
        self.assertEqual(staff_user.company, self.company_a)
        self.assertTrue(staff_user.check_password(PASSWORD))

    def test_company_admin_cannot_use_admin_to_grant_super_admin_role(self):
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=("is_staff",))
        self.client.force_login(self.staff_user)

        response = self.client.get("/admin/accounts/user/add/")

        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/admin/accounts/user/add/",
            {
                "phone": "+998908888889",
                "role": User.Role.SUPER_ADMIN,
                "company": "",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(phone="+998908888889").exists())
