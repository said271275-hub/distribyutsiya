from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import PhoneOTP
from apps.accounts.services import send_registration_otp
from apps.audit.models import AuditLog
from apps.companies.admin import approve_companies, reject_companies, suspend_companies
from apps.companies.models import Company


User = get_user_model()


class CompanyRegistrationAndMeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.phone = "+998901234567"
        self.password = "StrongPass123!"

    def _prepare_otp(self, phone):
        send_registration_otp(phone)
        otp = PhoneOTP.objects.filter(phone=phone).order_by("-created_at").first()
        return otp

    def test_company_registration_success(self):
        self._prepare_otp(self.phone)
        payload = {
            "name": "Baraka Savdo MChJ",
            "description": "Ichimliklar distribyutsiyasi",
            "service_districts": ["Guliston sh.", "Boyovut"],
            "tax_id": "123456789",
            "contact_phone": "+998901234567",
            "admin_phone": self.phone,
            "code": "123456",
            "password": self.password,
            "auto_approve_subscriptions": True,
        }
        response = self.client.post("/api/v1/companies/register/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["company"]["status"], Company.Status.PENDING)
        self.assertTrue(response.data["company"]["slug"])

        company = Company.objects.get(name="Baraka Savdo MChJ")
        self.assertEqual(company.status, Company.Status.PENDING)
        self.assertTrue(company.auto_approve_subscriptions)

        user = User.objects.get(phone=self.phone)
        self.assertEqual(user.role, User.Role.COMPANY_ADMIN)
        self.assertEqual(user.company, company)

        audit = AuditLog.objects.filter(action="company_registered", entity_id=str(company.pk)).first()
        self.assertIsNotNone(audit)

    def test_company_registration_duplicate_name_case_insensitive(self):
        Company.objects.create(name="Baraka Savdo", status=Company.Status.ACTIVE)
        self._prepare_otp(self.phone)
        payload = {
            "name": "baraka savdo",
            "admin_phone": self.phone,
            "code": "123456",
            "password": self.password,
        }
        response = self.client.post("/api/v1/companies/register/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.data)

    def test_company_registration_duplicate_phone(self):
        User.objects.create_user(phone=self.phone, password=self.password, role=User.Role.SHOP_OWNER)
        payload = {
            "name": "Yangi Kompaniya",
            "admin_phone": self.phone,
            "code": "123456",
            "password": self.password,
        }
        response = self.client.post("/api/v1/companies/register/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("admin_phone", response.data)

    def test_company_registration_invalid_otp(self):
        self._prepare_otp(self.phone)
        payload = {
            "name": "Yangi Kompaniya",
            "admin_phone": self.phone,
            "code": "999999",
            "password": self.password,
        }
        response = self.client.post("/api/v1/companies/register/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)

    def test_pending_company_admin_profile_and_status_immutable(self):
        company = Company.objects.create(name="Pending MChJ", status=Company.Status.PENDING)
        user = User.objects.create_user(
            phone=self.phone, password=self.password, role=User.Role.COMPANY_ADMIN, company=company
        )
        self.client.force_authenticate(user=user)

        # GET /api/v1/company/me/
        response = self.client.get("/api/v1/company/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Company.Status.PENDING)

        # PATCH /api/v1/company/me/ — attempt to change status to active
        patch_res = self.client.patch("/api/v1/company/me/", {"status": "active", "description": "Yangi izoh"})
        self.assertEqual(patch_res.status_code, 200)
        company.refresh_from_db()
        self.assertEqual(company.status, Company.Status.PENDING)
        self.assertEqual(company.description, "Yangi izoh")

    def test_rejected_and_suspended_company_admin_blocked_from_panel(self):
        company = Company.objects.create(
            name="Blocked MChJ",
            status=Company.Status.REJECTED,
            rejection_reason="Hujjatlar soxta deb topildi.",
        )
        user = User.objects.create_user(
            phone=self.phone, password=self.password, role=User.Role.COMPANY_ADMIN, company=company
        )
        self.client.force_authenticate(user=user)

        # Still can view /company/me/ to see reason
        me_res = self.client.get("/api/v1/company/me/")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.data["rejection_reason"], "Hujjatlar soxta deb topildi.")

        # Blocked from admin panel endpoints
        panel_res = self.client.get("/api/v1/admin/orders/")
        self.assertEqual(panel_res.status_code, 403)
        self.assertIn("Hujjatlar soxta", str(panel_res.data))

    def test_super_admin_company_actions_and_audit(self):
        super_admin = User.objects.create_superuser(phone="+998990000001", password=self.password)
        company = Company.objects.create(name="Tasdiq MChJ", status=Company.Status.PENDING)

        class MockRequest:
            user = super_admin

        # Approve
        approve_companies(None, MockRequest(), Company.objects.filter(pk=company.pk))
        company.refresh_from_db()
        self.assertEqual(company.status, Company.Status.ACTIVE)
        self.assertTrue(AuditLog.objects.filter(action="company_approved", entity_id=str(company.pk)).exists())

        # Suspend
        suspend_companies(None, MockRequest(), Company.objects.filter(pk=company.pk))
        company.refresh_from_db()
        self.assertEqual(company.status, Company.Status.SUSPENDED)
        self.assertTrue(AuditLog.objects.filter(action="company_suspended", entity_id=str(company.pk)).exists())

        # Reject
        reject_companies(None, MockRequest(), Company.objects.filter(pk=company.pk))
        company.refresh_from_db()
        self.assertEqual(company.status, Company.Status.REJECTED)
        self.assertTrue(AuditLog.objects.filter(action="company_rejected", entity_id=str(company.pk)).exists())
