from decimal import Decimal

from rest_framework.test import APIClient
from django.test import TestCase

from apps.accounts.models import User
from apps.companies.models import Company, CompanyShopLink, Shop


class SubscriptionsAndShopsListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Kompaniya A", status=Company.Status.ACTIVE)
        cls.other = Company.objects.create(name="Kompaniya B", status=Company.Status.ACTIVE)
        cls.admin = User.objects.create_user(
            phone="+998900007001", password="x", role=User.Role.COMPANY_ADMIN, company=cls.company
        )

    def make_shop(self, n, name):
        owner = User.objects.create_user(phone=f"+99890000710{n}", role=User.Role.SHOP_OWNER)
        return Shop.objects.create(
            owner=owner, name=name, phone_primary=f"+99890000720{n}", address="Guliston",
            district="Guliston", latitude=Decimal("40.84"), longitude=Decimal("68.66"),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_subscriptions_list_returns_links_for_each_status(self):
        active = self.make_shop(1, "Faol do‘kon")
        pending = self.make_shop(2, "Kutayotgan do‘kon")
        CompanyShopLink.objects.create(company=self.company, shop=active, status=CompanyShopLink.Status.ACTIVE)
        CompanyShopLink.objects.create(company=self.company, shop=pending)
        everything = self.client.get("/api/v1/company/subscriptions/").json()
        rows = everything["results"] if isinstance(everything, dict) else everything
        self.assertEqual({row["shop_name"] for row in rows}, {"Faol do‘kon", "Kutayotgan do‘kon"})
        only_active = self.client.get("/api/v1/company/subscriptions/?status=active").json()
        rows = only_active["results"] if isinstance(only_active, dict) else only_active
        self.assertEqual([row["shop_name"] for row in rows], ["Faol do‘kon"])

    def test_shop_list_excludes_shop_whose_link_to_this_company_is_inactive(self):
        """Boshqa kompaniyadagi faol obuna bu kompaniyaning ro'yxatiga o'tib qolmasligi kerak."""
        shop = self.make_shop(3, "Arxivlangan do‘kon")
        CompanyShopLink.objects.create(
            company=self.company, shop=shop, status=CompanyShopLink.Status.BLOCKED, is_active=False
        )
        CompanyShopLink.objects.create(
            company=self.other, shop=shop, status=CompanyShopLink.Status.ACTIVE, is_active=True
        )
        names = [row["name"] for row in self._rows("/api/v1/admin/shops/")]
        self.assertNotIn("Arxivlangan do‘kon", names)

    def test_shop_list_active_filter_checks_the_same_link(self):
        shop = self.make_shop(4, "Faol do‘kon")
        CompanyShopLink.objects.create(
            company=self.company, shop=shop, status=CompanyShopLink.Status.ACTIVE, is_active=True
        )
        names = [row["name"] for row in self._rows("/api/v1/admin/shops/?status=active")]
        self.assertIn("Faol do‘kon", names)

    def _rows(self, url):
        data = self.client.get(url).json()
        return data["results"] if isinstance(data, dict) else data
