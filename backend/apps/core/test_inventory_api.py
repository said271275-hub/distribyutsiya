from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import Company
from apps.core.models import InventoryEntry, ProductStock


class InventoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Kompaniya A")
        cls.other_company = Company.objects.create(name="Kompaniya B")
        cls.admin = User.objects.create_user(
            phone="+998901230001",
            role=User.Role.COMPANY_ADMIN,
            company=cls.company,
        )
        cls.other_admin = User.objects.create_user(
            phone="+998901230002",
            role=User.Role.COMPANY_ADMIN,
            company=cls.other_company,
        )
        cls.driver = User.objects.create_user(
            phone="+998901230003",
            role=User.Role.DRIVER,
            company=cls.company,
        )
        cls.owner = User.objects.create_user(
            phone="+998901230004",
            role=User.Role.SHOP_OWNER,
        )
        cls.super_admin = User.objects.create_user(
            phone="+998901230005",
            role=User.Role.SUPER_ADMIN,
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name="Suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
        )
        cls.other_product = Product.objects.create(
            company=cls.other_company,
            name="Sharbat",
            unit=Product.Unit.BOX,
            price=Decimal("1200.00"),
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def post_receipt(self, quantity="5.00"):
        return self.client.post(
            "/api/v1/admin/inventory/receipt/",
            {
                "product_id": self.product.pk,
                "quantity": quantity,
                "batch_number": "A-17",
                "date": date.today().isoformat(),
                "note": "Yetkazib beruvchidan",
            },
            format="json",
        )

    def assert_stock_matches_journal(self):
        stock = ProductStock.objects.get(company=self.company, product=self.product)
        totals = InventoryEntry.objects.filter(
            company=self.company, product=self.product
        ).aggregate(
            quantity=Sum("quantity_delta"),
            reserved=Sum("reserved_delta"),
        )
        self.assertEqual(stock.current_quantity, totals["quantity"] or Decimal("0.00"))
        self.assertEqual(stock.reserved_quantity, totals["reserved"] or Decimal("0.00"))
        return stock

    def test_receipt_and_issue_adjust_stock_in_decimal_quantities(self):
        received = self.post_receipt("5.75")
        self.assertEqual(received.status_code, 201, received.data)
        self.assertEqual(received.data["batch_number"], "A-17")
        self.assertEqual(self.assert_stock_matches_journal().current_quantity, Decimal("5.75"))

        issued = self.client.post(
            "/api/v1/admin/inventory/issue/",
            {
                "product_id": self.product.pk,
                "quantity": "2.25",
                "reason": "Boshqa omborga berildi",
            },
            format="json",
        )
        self.assertEqual(issued.status_code, 201, issued.data)
        self.assertEqual(issued.data["quantity_delta"], "-2.25")
        self.assertEqual(self.assert_stock_matches_journal().current_quantity, Decimal("3.50"))

    def test_adjustment_is_corrected_by_an_append_only_reversal(self):
        self.assertEqual(self.post_receipt().status_code, 201)
        adjusted = self.client.post(
            "/api/v1/admin/inventory/adjustment/",
            {
                "product_id": self.product.pk,
                "quantity_delta": "-2.00",
                "reason": "lost",
                "note": "Sanashda aniqlandi",
            },
            format="json",
        )
        self.assertEqual(adjusted.status_code, 201, adjusted.data)
        self.assertEqual(self.assert_stock_matches_journal().current_quantity, Decimal("3.00"))

        reversed_entry = self.client.post(
            f"/api/v1/admin/inventory-entries/{adjusted.data['id']}/reverse/",
            {"reason": "Noto‘g‘ri sanash"},
            format="json",
        )
        self.assertEqual(reversed_entry.status_code, 201, reversed_entry.data)
        self.assertEqual(reversed_entry.data["quantity_delta"], "2.00")
        self.assertEqual(reversed_entry.data["reversal_of_id"], adjusted.data["id"])
        self.assertEqual(self.assert_stock_matches_journal().current_quantity, Decimal("5.00"))
        self.assertEqual(
            self.client.post(
                f"/api/v1/admin/inventory-entries/{adjusted.data['id']}/reverse/",
                {"reason": "Yana takrorlash"},
                format="json",
            ).status_code,
            400,
        )
        entry = InventoryEntry.objects.get(pk=adjusted.data["id"])
        entry.reason = "O‘zgartirishga urinish"
        with self.assertRaises(TypeError):
            entry.save()
        with self.assertRaises(TypeError):
            InventoryEntry.objects.filter(pk=entry.pk).update(reason="O‘zgartirishga urinish")
        with self.assertRaises(TypeError):
            InventoryEntry.objects.filter(pk=entry.pk).delete()

    def test_negative_receipt_is_rejected_without_changing_stock(self):
        response = self.post_receipt("-1.00")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(InventoryEntry.objects.exists())
        self.assertFalse(ProductStock.objects.exists())

    def test_minimum_stock_setting_and_movement_history_are_company_scoped(self):
        received = self.post_receipt("5.00")
        self.assertEqual(received.status_code, 201)
        minimum = self.client.patch(
            f"/api/v1/admin/inventory/{self.product.pk}/minimum/",
            {"minimum_quantity": "5.00"},
            format="json",
        )
        self.assertEqual(minimum.status_code, 200, minimum.data)
        self.assertTrue(minimum.data["is_low_stock"])

        history = self.client.get(
            "/api/v1/admin/inventory-entries/",
            {"product_id": self.product.pk},
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data["count"], 1)

        self.client.force_authenticate(self.other_admin)
        stocks = self.client.get("/api/v1/admin/inventory/")
        self.assertEqual(stocks.status_code, 200)
        self.assertEqual(
            [row["product_id"] for row in stocks.data["results"]],
            [self.other_product.pk],
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/admin/inventory-entries/{received.data['id']}/"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/admin/inventory-entries/{received.data['id']}/reverse/",
                {"reason": "IDOR sinovi"},
                format="json",
            ).status_code,
            404,
        )
        hidden_receipt = self.post_receipt()
        self.assertEqual(hidden_receipt.status_code, 404)

    def test_driver_and_shop_owner_cannot_read_or_write_inventory(self):
        for user in (self.driver, self.owner, self.super_admin):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get("/api/v1/admin/inventory/").status_code, 403)
            self.assertEqual(self.post_receipt().status_code, 403)
