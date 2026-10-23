from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import Payment, ShopBalance


class ShopApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Sirdaryo", contact_phone="+998900000001")
        cls.other_company = Company.objects.create(name="Boshqa kompaniya")
        cls.owner = User.objects.create_user(
            phone="+998900000010", password="StrongPassword!234", role=User.Role.SHOP_OWNER
        )
        cls.shop = Shop.objects.create(
            owner=cls.owner,
            name="Guliston market",
            owner_name="Dilnoza",
            phone_primary="+998900000011",
            address="Markaz",
            district="Guliston",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        CompanyShopLink.objects.create(company=cls.company, shop=cls.shop)
        cls.product = Product.objects.create(
            company=cls.company,
            name="Suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
        )
        cls.other_product = Product.objects.create(
            company=cls.other_company,
            name="Yopiq mahsulot",
            unit=Product.Unit.PIECE,
            price=Decimal("9000.00"),
        )
        ShopPrice.objects.create(
            company=cls.company,
            shop=cls.shop,
            product=cls.product,
            price=Decimal("800.00"),
            discount_percent=Decimal("10.00"),
        )
        cls.other_owner = User.objects.create_user(
            phone="+998900000020", password="StrongPassword!234", role=User.Role.SHOP_OWNER
        )
        cls.other_shop = Shop.objects.create(
            owner=cls.other_owner,
            name="Boshqa do‘kon",
            phone_primary="+998900000021",
            address="Boshqa manzil",
            district="Yangiyer",
            latitude=Decimal("40.850000"),
            longitude=Decimal("68.670000"),
        )
        CompanyShopLink.objects.create(company=cls.other_company, shop=cls.other_shop)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def order_payload(self, **overrides):
        data = {
            "company_id": self.company.pk,
            "delivery_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "items": [{
                "product_id": self.product.pk,
                "quantity": "2.00",
                "unit_price": "0.01",
            }],
        }
        data.update(overrides)
        return data

    def test_shop_owner_can_update_only_editable_profile_fields(self):
        response = self.client.patch(
            "/api/v1/shop/profile/",
            {"name": "Yangi nom", "owner_name": "Malika", "owner": self.other_owner.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Yangi nom")
        self.assertEqual(self.shop.owner_name, "Malika")
        self.assertEqual(self.shop.owner_id, self.owner.pk)

    def test_new_shop_owner_can_select_company_and_create_profile(self):
        new_owner = User.objects.create_user(
            phone="+998900000030", password="StrongPassword!234", role=User.Role.SHOP_OWNER
        )
        self.client.force_authenticate(new_owner)

        companies = self.client.get("/api/v1/shop/companies/")
        self.assertEqual(companies.status_code, 200)
        self.assertEqual(
            {row["id"] for row in companies.data},
            {self.company.pk, self.other_company.pk},
        )

        response = self.client.post(
            "/api/v1/shop/profile/",
            {
                "company_id": self.company.pk,
                "name": "Yangi do‘kon",
                "owner_name": "Aziza",
                "phone_primary": "+998900000031",
                "phone_secondary": "",
                "address": "Markaz ko‘chasi",
                "district": "Guliston",
                "latitude": "40.840000",
                "longitude": "68.660000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        shop = Shop.objects.get(owner=new_owner)
        self.assertTrue(CompanyShopLink.objects.filter(company=self.company, shop=shop).exists())
        duplicate = self.client.post(
            "/api/v1/shop/profile/",
            {
                "company_id": self.company.pk,
                "name": "Ikkinchi do‘kon",
                "owner_name": "Aziza",
                "phone_primary": "+998900000032",
                "address": "Markaz ko‘chasi",
                "district": "Guliston",
                "latitude": "40.840000",
                "longitude": "68.660000",
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_order_rejects_a_company_not_linked_to_the_shop(self):
        response = self.client.post(
            "/api/v1/orders/",
            self.order_payload(company_id=self.other_company.pk),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_catalog_shows_only_linked_companies_and_effective_discounted_price(self):
        response = self.client.get("/api/v1/catalog/")

        self.assertEqual(response.status_code, 200)
        products = response.data["results"]
        self.assertEqual([item["id"] for item in products], [self.product.pk])
        self.assertEqual(products[0]["base_price"], "1000.00")
        self.assertEqual(products[0]["unit_price"], "720.00")
        self.assertEqual(products[0]["discount_percent"], "10.00")

    def test_catalog_search_and_company_filter_are_server_side(self):
        response = self.client.get(
            "/api/v1/catalog/", {"search": "Suv", "company": self.company.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["results"]], [self.product.pk])

    def test_order_uses_server_price_and_records_initial_status(self):
        before_cutoff = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(17, 0)),
            timezone.get_current_timezone(),
        )
        with patch("apps.orders.shop_services.timezone.localtime", return_value=before_cutoff):
            response = self.client.post(
                "/api/v1/orders/", self.order_payload(), format="json"
            )

        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["id"])
        item = order.items.get()
        self.assertEqual(item.unit_price, Decimal("720.00"))
        self.assertEqual(item.line_total, Decimal("1440.00"))
        self.assertEqual(order.total_price, Decimal("1440.00"))
        self.assertEqual(
            list(order.status_history.values_list("status", flat=True)),
            [Order.Status.NEW],
        )

    def test_next_day_order_is_rejected_after_company_cutoff(self):
        cutoff_time = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(18, 1)),
            timezone.get_current_timezone(),
        )
        with patch("apps.orders.shop_services.timezone.localtime", return_value=cutoff_time):
            response = self.client.post(
                "/api/v1/orders/", self.order_payload(), format="json"
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("18:00", str(response.data))
        self.assertFalse(Order.objects.exists())

    def test_shop_owner_cannot_read_another_shop_order(self):
        order = Order.objects.create(
            company=self.other_company,
            shop=self.other_shop,
            delivery_date=timezone.localdate() + timedelta(days=1),
        )

        response = self.client.get(f"/api/v1/orders/{order.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_owner_can_cancel_new_order_but_not_confirmed_order(self):
        order = Order.objects.create(
            company=self.company,
            shop=self.shop,
            delivery_date=timezone.localdate() + timedelta(days=1),
        )
        cancelled = self.client.post(f"/api/v1/orders/{order.pk}/cancel/", {}, format="json")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data["status"], Order.Status.CANCELLED)
        self.assertEqual(
            list(OrderStatusHistory.objects.filter(order=order).values_list("status", flat=True)),
            [Order.Status.CANCELLED],
        )

        order.status = Order.Status.CONFIRMED
        order.save(update_fields=("status", "updated_at"))
        denied = self.client.post(f"/api/v1/orders/{order.pk}/cancel/", {}, format="json")
        self.assertEqual(denied.status_code, 400)

    def test_order_can_be_edited_and_repeated_with_fresh_server_pricing(self):
        before_cutoff = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(17, 0)),
            timezone.get_current_timezone(),
        )
        with patch("apps.orders.shop_services.timezone.localtime", return_value=before_cutoff):
            created = self.client.post(
                "/api/v1/orders/", self.order_payload(), format="json"
            )
            order_id = created.data["id"]
            edited = self.client.patch(
                f"/api/v1/orders/{order_id}/",
                {
                    "note": "Eshik yoniga olib keling",
                    "items": [{"product_id": self.product.pk, "quantity": "3"}],
                },
                format="json",
            )
            self.assertEqual(edited.status_code, 200)
            self.assertEqual(edited.data["total_price"], "2160.00")

            repeated = self.client.post(
                f"/api/v1/orders/{order_id}/repeat/",
                {"delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat()},
                format="json",
            )
        self.assertEqual(repeated.status_code, 201, repeated.data)
        self.assertNotEqual(repeated.data["id"], order_id)
        self.assertEqual(repeated.data["total_price"], "2160.00")

    def test_repeat_last_order_cart_uses_current_prices_and_omits_inactive_products(self):
        older_order = Order.objects.create(
            company=self.company,
            shop=self.shop,
            delivery_date=timezone.localdate() + timedelta(days=1),
        )
        latest_order = Order.objects.create(
            company=self.company,
            shop=self.shop,
            delivery_date=timezone.localdate() + timedelta(days=2),
        )
        Order.objects.filter(pk=older_order.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        inactive_product = Product.objects.create(
            company=self.company,
            name="Nofaol mahsulot",
            unit=Product.Unit.PIECE,
            price=Decimal("500.00"),
            is_active=False,
        )
        OrderItem.objects.create(
            company=self.company,
            order=older_order,
            product=self.product,
            quantity=Decimal("1.00"),
            unit_price=Decimal("600.00"),
        )
        OrderItem.objects.create(
            company=self.company,
            order=latest_order,
            product=self.product,
            quantity=Decimal("3.00"),
            unit_price=Decimal("600.00"),
        )
        OrderItem.objects.create(
            company=self.company,
            order=latest_order,
            product=inactive_product,
            quantity=Decimal("2.00"),
            unit_price=Decimal("500.00"),
        )

        response = self.client.get("/api/v1/orders/repeat-cart/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["omitted_count"], 1)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["product"]["id"], self.product.pk)
        self.assertEqual(response.data["items"][0]["quantity"], Decimal("3.00"))
        self.assertEqual(response.data["items"][0]["product"]["unit_price"], "720.00")

    def test_repeat_last_order_cart_is_empty_when_shop_has_no_orders(self):
        response = self.client.get("/api/v1/orders/repeat-cart/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"items": [], "omitted_count": 0})

    def test_finance_endpoint_is_read_only_and_scoped_to_owner_shop(self):
        ShopBalance.objects.create(
            company=self.company, shop=self.shop, current_balance=Decimal("1250.00")
        )
        Payment.objects.create(
            company=self.company,
            shop=self.shop,
            amount=Decimal("500.00"),
            method=Payment.Method.CASH,
        )

        response = self.client.get("/api/v1/shop/finance/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], "1250.00")
        self.assertEqual(len(response.data["payments"]), 1)