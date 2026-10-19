import os
import secrets
import subprocess
import sys
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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
from apps.accounts.sms import DevOtpProvider, get_otp_provider
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
        response = self.client.post(
            "/api/auth/staff/login/" if staff else "/api/auth/login/",
            {"phone": phone or (self.staff_user.phone if staff else self.shop_user.phone),
             "password": PASSWORD},
            format="json",
        )
        return response

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

    def test_dev_otp_is_rejected_during_production_settings_load(self):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SECRET_KEY="test-only-secret-key-long-enough-for-hmac",
            DJANGO_DEBUG="False",
            DEV_OTP_ENABLED="True",
            DEV_OTP_CODE=DEV_TEST_OTP_CODE,
        )
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ImproperlyConfigured", result.stderr)
        self.assertIn("DEV_OTP_ENABLED", result.stderr)

    def test_dev_staff_password_is_rejected_without_local_otp_flags(self):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SECRET_KEY="test-only-secret-key-long-enough-for-hmac",
            DJANGO_DEBUG="False",
            DEV_OTP_ENABLED="False",
            DEV_STAFF_PASSWORD="temporary-test-password",
        )
        result = subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEV_STAFF_PASSWORD", result.stderr)

    def test_five_failed_logins_create_a_temporary_block(self):
        for index in range(5):
            response = self.client.post(
                "/api/auth/login/",
                {"phone": self.shop_user.phone, "password": f"wrong-{index}"},
                format="json",
            )
            self.assertEqual(response.status_code, 401)
        attempt = LoginAttempt.objects.get(
            phone=self.shop_user.phone, scope="shop"
        )
        self.assertEqual(attempt.failures, 5)
        self.assertGreater(attempt.blocked_until, timezone.now())
        self.assertIn("vaqtincha bloklangan", str(self.client.post(
            "/api/auth/login/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
            format="json",
        ).data["detail"]).lower())

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
            {"reason": "not_needed", "password": PASSWORD},
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
            {"reason": "not_needed", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(blocked_by_debt.status_code, 400)
        self.assertIn("qarz", str(blocked_by_debt.data).lower())

    def test_account_deletion_requires_the_current_password_and_reason(self):
        self.order_a.status = Order.Status.DELIVERED
        self.order_a.save(update_fields=("status", "updated_at"))
        login = self.login()
        self.bearer_client(login.data["access"])

        wrong_password = self.client.post(
            "/api/auth/me/deletion/",
            {"reason": "not_needed", "password": "wrong-password"},
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
            {"password": PASSWORD},
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
        requested = self.client.post(
            "/api/auth/me/deletion/",
            {
                "reason": "other",
                "reason_other": "Boshqa sabab",
                "password": PASSWORD,
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
        restored = self.client.post(
            "/api/auth/restore/",
            {"phone": self.shop_user.phone, "password": PASSWORD},
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
