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


class CompanySubscriptionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "StrongPass123!"
        self.company1 = Company.objects.create(
            name="Sirdaryo Cola",
            status=Company.Status.ACTIVE,
            service_districts=["Guliston", "Boyovut"],
            contact_phone="+998901111111",
        )
        self.company2 = Company.objects.create(
            name="Jizzax Suvlari",
            status=Company.Status.ACTIVE,
            auto_approve_subscriptions=True,
            service_districts=["Guliston"],
            contact_phone="+998902222222",
        )
        self.pending_company = Company.objects.create(
            name="Kutilayotgan MChJ",
            status=Company.Status.PENDING,
        )
        self.admin1 = User.objects.create_user(
            phone="+998901111111", password=self.password, role=User.Role.COMPANY_ADMIN, company=self.company1
        )
        self.admin2 = User.objects.create_user(
            phone="+998902222222", password=self.password, role=User.Role.COMPANY_ADMIN, company=self.company2
        )
        self.shop_owner = User.objects.create_user(
            phone="+998903333333", password=self.password, role=User.Role.SHOP_OWNER
        )
        from apps.companies.models import Shop, CompanyShopLink
        self.shop = Shop.objects.create(
            owner=self.shop_owner,
            name="Bahor Do‘koni",
            owner_name="Ali Valiyev",
            phone_primary="+998903333333",
            address="Mustaqillik ko‘chasi, 12",
            district="Guliston",
            latitude=40.5,
            longitude=68.7,
        )

    def test_directory_search_only_active_companies(self):
        self.client.force_authenticate(user=self.shop_owner)
        res = self.client.get("/api/v1/directory/companies/")
        self.assertEqual(res.status_code, 200)
        names = [item["name"] for item in res.data["results"]]
        self.assertIn("Sirdaryo Cola", names)
        self.assertIn("Jizzax Suvlari", names)
        self.assertNotIn("Kutilayotgan MChJ", names)

        # Search by query
        search_res = self.client.get("/api/v1/directory/companies/?q=cola")
        self.assertEqual(search_res.status_code, 200)
        self.assertEqual(len(search_res.data["results"]), 1)
        self.assertEqual(search_res.data["results"][0]["name"], "Sirdaryo Cola")

    def test_subscribe_flow_manual_and_auto_approve(self):
        from apps.companies.models import CompanyShopLink
        self.client.force_authenticate(user=self.shop_owner)

        # 1. Manual approval company -> pending
        res1 = self.client.post(f"/api/v1/directory/companies/{self.company1.id}/subscribe/")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data["status"], "pending")
        self.assertFalse(res1.data["is_active"])

        # Duplicate subscribe -> 400
        dup_res = self.client.post(f"/api/v1/directory/companies/{self.company1.id}/subscribe/")
        self.assertEqual(dup_res.status_code, 400)

        # 2. Auto-approve company -> active immediately
        res2 = self.client.post(f"/api/v1/directory/companies/{self.company2.id}/subscribe/")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["status"], "active")
        self.assertTrue(res2.data["is_active"])

        # Check my companies
        my_res = self.client.get("/api/v1/my/companies/")
        self.assertEqual(my_res.status_code, 200)
        self.assertEqual(len(my_res.data), 2)

    def test_privacy_phone_and_address_hidden_until_active(self):
        from apps.companies.models import CompanyShopLink
        link = CompanyShopLink.objects.create(
            company=self.company1,
            shop=self.shop,
            status=CompanyShopLink.Status.PENDING,
            is_active=False,
        )

        # Company 1 admin views pending requests
        self.client.force_authenticate(user=self.admin1)
        res = self.client.get("/api/v1/company/subscriptions/?status=pending")
        self.assertEqual(res.status_code, 200)
        req_data = res.data[0]
        self.assertEqual(req_data["shop_name"], "Bahor Do‘koni")
        self.assertEqual(req_data["district"], "Guliston")
        # Hidden privacy fields
        self.assertIsNone(req_data["phone_primary"])
        self.assertIsNone(req_data["address"])

        # Approve subscription
        approve_res = self.client.post(f"/api/v1/company/subscriptions/{link.id}/approve/")
        self.assertEqual(approve_res.status_code, 200)
        self.assertEqual(approve_res.data["status"], "active")
        # Now privacy fields revealed!
        self.assertEqual(approve_res.data["phone_primary"], "+998903333333")
        self.assertEqual(approve_res.data["address"], "Mustaqillik ko‘chasi, 12")

    def test_company_admin_reject_and_block_flow(self):
        from apps.companies.models import CompanyShopLink
        link = CompanyShopLink.objects.create(
            company=self.company1,
            shop=self.shop,
            status=CompanyShopLink.Status.PENDING,
            is_active=False,
        )

        self.client.force_authenticate(user=self.admin1)
        # Reject with reason
        reject_res = self.client.post(
            f"/api/v1/company/subscriptions/{link.id}/reject/",
            {"reject_reason": "Yetkazish hududimizdan tashqarida"},
            format="json",
        )
        self.assertEqual(reject_res.status_code, 200)
        self.assertEqual(reject_res.data["status"], "rejected")
        self.assertEqual(reject_res.data["reject_reason"], "Yetkazish hududimizdan tashqarida")

        # Block
        block_res = self.client.post(f"/api/v1/company/subscriptions/{link.id}/block/")
        self.assertEqual(block_res.status_code, 200)
        self.assertEqual(block_res.data["status"], "blocked")

        # Blocked shop tries to subscribe again -> 400
        self.client.force_authenticate(user=self.shop_owner)
        sub_res = self.client.post(f"/api/v1/directory/companies/{self.company1.id}/subscribe/")
        self.assertEqual(sub_res.status_code, 400)
        self.assertIn("bloklangan", str(sub_res.data))

    def test_idor_company_cannot_manage_another_company_subscription(self):
        from apps.companies.models import CompanyShopLink
        link = CompanyShopLink.objects.create(
            company=self.company1,
            shop=self.shop,
            status=CompanyShopLink.Status.PENDING,
            is_active=False,
        )
        # Company 2 admin tries to approve Company 1's link
        self.client.force_authenticate(user=self.admin2)
        res = self.client.post(f"/api/v1/company/subscriptions/{link.id}/approve/")
        self.assertEqual(res.status_code, 404)

    def test_unsubscribe_debt_and_order_restrictions(self):
        from apps.companies.models import CompanyShopLink
        from apps.orders.models import Order
        from apps.payments.models import ShopBalance
        from decimal import Decimal
        from datetime import date, timedelta

        link = CompanyShopLink.objects.create(
            company=self.company1,
            shop=self.shop,
            status=CompanyShopLink.Status.ACTIVE,
            is_active=True,
        )
        self.client.force_authenticate(user=self.shop_owner)

        # 1. With open order -> cannot unsubscribe
        order = Order.objects.create(
            company=self.company1,
            shop=self.shop,
            delivery_date=date.today() + timedelta(days=1),
            status=Order.Status.NEW,
        )
        del_res = self.client.delete(f"/api/v1/directory/companies/{self.company1.id}/subscribe/")
        self.assertEqual(del_res.status_code, 400)
        self.assertIn("ochiq buyurtma", str(del_res.data))

        # Close order
        order.status = Order.Status.CANCELLED
        order.save()

        # 2. With debt -> cannot unsubscribe
        ShopBalance.objects.create(
            company=self.company1,
            shop=self.shop,
            current_balance=Decimal("-50000.00"),
        )
        del_res2 = self.client.delete(f"/api/v1/directory/companies/{self.company1.id}/subscribe/")
        self.assertEqual(del_res2.status_code, 400)
        self.assertIn("qarzdor", str(del_res2.data))

        # Clear debt -> success unsubscribe
        ShopBalance.objects.filter(company=self.company1, shop=self.shop).update(current_balance=Decimal("0.00"))
        del_res3 = self.client.delete(f"/api/v1/directory/companies/{self.company1.id}/subscribe/")
        self.assertEqual(del_res3.status_code, 200)
        link.refresh_from_db()
        self.assertFalse(link.is_active)

