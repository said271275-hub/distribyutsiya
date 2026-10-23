from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.catalog.models import ContainerMovement, Product, ReturnableContainer
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.logistics.models import DriverProfile, Trip, TripStop, Vehicle
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import BalanceEntry, Payment, ShopBalance


class AdminApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="Kompaniya A")
        cls.other_company = Company.objects.create(name="Kompaniya B")
        cls.admin = User.objects.create_user(
            phone="+998900004001",
            password="test-admin-password",
            role=User.Role.COMPANY_ADMIN,
            company=cls.company,
        )
        cls.other_admin = User.objects.create_user(
            phone="+998900004002",
            password="test-admin-password",
            role=User.Role.COMPANY_ADMIN,
            company=cls.other_company,
        )
        cls.owner = User.objects.create_user(
            phone="+998900004003", password="test-shop-password", role=User.Role.SHOP_OWNER
        )
        cls.shop = Shop.objects.create(
            owner=cls.owner,
            name="A do‘kon",
            phone_primary="+998900004004",
            address="Guliston",
            district="Guliston",
            latitude=Decimal("40.840000"),
            longitude=Decimal("68.660000"),
        )
        CompanyShopLink.objects.create(company=cls.company, shop=cls.shop)
        ShopBalance.objects.create(
            company=cls.company, shop=cls.shop, credit_limit=Decimal("5000.00")
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name="Suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
            unit_weight=Decimal("10.000"),
            unit_volume=Decimal("5.000"),
        )
        cls.other_owner = User.objects.create_user(
            phone="+998900004005", role=User.Role.SHOP_OWNER
        )
        cls.other_shop = Shop.objects.create(
            owner=cls.other_owner,
            name="B do‘kon",
            phone_primary="+998900004006",
            address="Yangiyer",
            district="Yangiyer",
            latitude=Decimal("40.850000"),
            longitude=Decimal("68.670000"),
        )
        CompanyShopLink.objects.create(company=cls.other_company, shop=cls.other_shop)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def make_order(self, company=None, shop=None, quantity="2.00", status=Order.Status.NEW):
        company = company or self.company
        shop = shop or self.shop
        order = Order.objects.create(
            company=company,
            shop=shop,
            status=status,
            delivery_date=date.today() + timedelta(days=1),
        )
        product = self.product
        OrderItem.objects.create(
            company=company,
            order=order,
            product=product,
            quantity=Decimal(quantity),
            unit_price=Decimal("1000.00"),
        )
        order.recalculate_total()
        return order

    def test_order_list_filters_and_is_scoped_to_admin_company(self):
        own_order = self.make_order()
        self.make_order(company=self.other_company, shop=self.other_shop)

        response = self.client.get(
            "/api/v1/admin/orders/",
            {"date": own_order.delivery_date.isoformat(), "district": "Guliston", "search": "A do‘kon"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [own_order.pk])
        self.assertEqual(response.data["results"][0]["shop_name"], self.shop.name)
        invalid = self.client.get("/api/v1/admin/orders/", {"date": "not-a-date"})
        self.assertEqual(invalid.status_code, 400)

    def test_confirmation_does_not_create_order_debt(self):
        order = self.make_order()
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.CONFIRMED, "reason": "Buyurtma tekshirildi"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        balance = ShopBalance.objects.get(company=self.company, shop=self.shop)
        self.assertEqual(balance.current_balance, Decimal("0.00"))
        self.assertFalse(BalanceEntry.objects.filter(order=order).exists())
        history = OrderStatusHistory.objects.get(order=order)
        self.assertEqual(history.from_status, Order.Status.NEW)
        self.assertEqual(history.status, Order.Status.CONFIRMED)

    def test_delivery_posts_debt_for_partially_delivered_quantities(self):
        order = self.make_order(quantity="2.00")
        self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.CONFIRMED, "reason": "Tasdiq"},
            format="json",
        )
        self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.LOADED, "reason": "Yuklandi"},
            format="json",
        )
        self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.IN_TRANSIT, "reason": "Yo‘lga chiqdi"},
            format="json",
        )
        item = order.items.get()
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {
                "status": Order.Status.DELIVERED,
                "reason": "Qisman yetkazildi",
                "delivered_items": [{"item_id": item.pk, "quantity": "1.25"}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["items"][0]["delivered_quantity"], "1.25")
        item.refresh_from_db()
        self.assertEqual(item.delivered_quantity, Decimal("1.25"))
        entry = BalanceEntry.objects.get(order=order)
        self.assertEqual(entry.direction, BalanceEntry.Direction.DEBIT)
        self.assertEqual(entry.amount, Decimal("1250.00"))
        self.assertIsNotNone(entry.posted_at)
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("1250.00"),
        )
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin, entity_type="Order", entity_id=str(order.pk)
        ).exists())

    def test_delivery_rejects_invalid_quantities_without_posting_debt(self):
        order = self.make_order(quantity="2.00")
        for target, reason in (
            (Order.Status.CONFIRMED, "Tasdiq"),
            (Order.Status.LOADED, "Yuklandi"),
            (Order.Status.IN_TRANSIT, "Yo‘lga chiqdi"),
        ):
            response = self.client.post(
                f"/api/v1/admin/orders/{order.pk}/status/",
                {"status": target, "reason": reason},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
        item = order.items.get()

        for quantity in ("2.01", "0.00"):
            response = self.client.post(
                f"/api/v1/admin/orders/{order.pk}/status/",
                {
                    "status": Order.Status.DELIVERED,
                    "reason": "Yetkazish miqdorini tekshirish",
                    "delivered_items": [{"item_id": item.pk, "quantity": quantity}],
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)

        order.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_TRANSIT)
        self.assertIsNone(item.delivered_quantity)
        self.assertFalse(BalanceEntry.objects.filter(order=order).exists())

    def test_invalid_order_transition_is_rejected(self):
        order = self.make_order()
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.LOADED, "reason": "Noto‘g‘ri sakrash"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.NEW)

    def test_credit_limit_requires_dispatcher_confirmation(self):
        order = self.make_order(quantity="6.00")
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.CONFIRMED, "reason": "Tasdiq"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(BalanceEntry.objects.filter(order=order).exists())
        for target, reason in (
            (Order.Status.LOADED, "Yuklandi"),
            (Order.Status.IN_TRANSIT, "Yo‘lga chiqdi"),
        ):
            response = self.client.post(
                f"/api/v1/admin/orders/{order.pk}/status/",
                {"status": target, "reason": reason},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {
                "status": Order.Status.DELIVERED,
                "reason": "Yetkazish",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("warning", response.data)
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.IN_TRANSIT)
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {
                "status": Order.Status.DELIVERED,
                "reason": "Limitdan oshishiga ruxsat",
                "allow_credit_limit_exceeded": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("6000.00"),
        )

    def test_undelivered_order_cancellation_does_not_create_debt(self):
        order = self.make_order()
        self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.CONFIRMED, "reason": "Tasdiq"},
            format="json",
        )
        response = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.CANCELLED, "reason": "Do‘kon so‘rovi"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("0.00"),
        )
        self.assertFalse(BalanceEntry.objects.filter(order=order).exists())

    def test_cancelling_delivered_order_reverses_delivered_debt(self):
        order = self.make_order(quantity="2.00")
        for target, reason in (
            (Order.Status.CONFIRMED, "Tasdiq"),
            (Order.Status.LOADED, "Yuklandi"),
            (Order.Status.IN_TRANSIT, "Yo‘lga chiqdi"),
        ):
            response = self.client.post(
                f"/api/v1/admin/orders/{order.pk}/status/",
                {"status": target, "reason": reason},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
        item = order.items.get()
        delivered = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {
                "status": Order.Status.DELIVERED,
                "reason": "Qisman yetkazildi",
                "delivered_items": [{"item_id": item.pk, "quantity": "1.25"}],
            },
            format="json",
        )
        self.assertEqual(delivered.status_code, 200, delivered.data)
        cancelled = self.client.post(
            f"/api/v1/admin/orders/{order.pk}/status/",
            {"status": Order.Status.CANCELLED, "reason": "Bekor qilindi"},
            format="json",
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        entries = list(BalanceEntry.objects.filter(order=order).order_by("pk"))
        self.assertEqual(
            [(entry.direction, entry.amount) for entry in entries],
            [
                (BalanceEntry.Direction.DEBIT, Decimal("1250.00")),
                (BalanceEntry.Direction.CREDIT, Decimal("1250.00")),
            ],
        )
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("0.00"),
        )

    def test_bulk_confirm_and_picking_totals(self):
        delivery_date = date.today() + timedelta(days=1)
        first = self.make_order(quantity="2.00", status=Order.Status.CONFIRMED)
        second = self.make_order(quantity="3.00", status=Order.Status.CONFIRMED)
        first.delivery_date = delivery_date
        first.save(update_fields=("delivery_date", "updated_at"))
        second.delivery_date = delivery_date
        second.save(update_fields=("delivery_date", "updated_at"))
        pending = self.make_order(quantity="100.00")
        pending.delivery_date = delivery_date + timedelta(days=1)
        pending.save(update_fields=("delivery_date", "updated_at"))
        ShopBalance.objects.filter(company=self.company, shop=self.shop).update(
            credit_limit=Decimal("200000.00")
        )
        bulk = self.client.post(
            "/api/v1/admin/orders/bulk-confirm/",
            {"order_ids": [pending.pk], "reason": "Ommaviy tasdiq"},
            format="json",
        )
        self.assertEqual(bulk.status_code, 200, bulk.data)
        self.assertEqual(Order.objects.get(pk=pending.pk).status, Order.Status.CONFIRMED)

        response = self.client.get(
            "/api/v1/admin/orders/picking-list/", {"date": delivery_date.isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["quantity"], "5.00")
        self.assertEqual(response.data["items"][0]["total_weight"], "50.000")
        self.assertEqual(response.data["items"][0]["total_volume"], "25.000")

    def test_product_and_shop_crud_are_company_scoped(self):
        Product.objects.create(
            company=self.other_company,
            name="B mahsulot",
            unit=Product.Unit.PIECE,
            price=Decimal("10.00"),
        )
        response = self.client.get("/api/v1/admin/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [self.product.pk])
        created = self.client.post(
            "/api/v1/admin/products/",
            {"name": "Yangi", "unit": Product.Unit.PIECE, "price": "25.00"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(Product.objects.get(pk=created.data["id"]).company, self.company)

    def test_company_admin_cannot_access_other_company_resources(self):
        other_product = Product.objects.create(
            company=self.other_company,
            name="B mahsulot",
            unit=Product.Unit.PIECE,
            price=Decimal("10.00"),
        )
        self.assertEqual(
            self.client.get(f"/api/v1/admin/products/{other_product.pk}/").status_code,
            404,
        )
        other_order = self.make_order(company=self.other_company, shop=self.other_shop)
        self.assertEqual(
            self.client.get(f"/api/v1/admin/orders/{other_order.pk}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/admin/orders/{other_order.pk}/status/",
                {"status": Order.Status.CONFIRMED, "reason": "Ruxsatsiz"},
                format="json",
            ).status_code,
            404,
        )

    def test_shop_price_vehicle_driver_and_shop_archive_apis(self):
        price = self.client.post(
            "/api/v1/admin/shop-prices/",
            {
                "shop": self.shop.pk,
                "product": self.product.pk,
                "price": "900.00",
                "discount_percent": "5.00",
            },
            format="json",
        )
        self.assertEqual(price.status_code, 201, price.data)
        self.assertEqual(ShopPrice.objects.get(pk=price.data["id"]).company, self.company)

        vehicle = self.client.post(
            "/api/v1/admin/vehicles/",
            {
                "name": "Yuk mashinasi",
                "plate_number": "01A200AA",
                "capacity": "1200.00",
                "volume_capacity": "18.50",
            },
            format="json",
        )
        self.assertEqual(vehicle.status_code, 201, vehicle.data)
        self.assertEqual(Vehicle.objects.get(pk=vehicle.data["id"]).company, self.company)
        self.assertEqual(vehicle.data["volume_capacity"], "18.50")

        driver_user = User.objects.create_user(
            phone="+998900004030", company=self.company, role=User.Role.DRIVER
        )
        driver = DriverProfile.objects.create(company=self.company, user=driver_user)
        updated_driver = self.client.patch(
            f"/api/v1/admin/drivers/{driver.pk}/",
            {"license_number": "ABC-123", "vehicle_id": vehicle.data["id"]},
            format="json",
        )
        self.assertEqual(updated_driver.status_code, 200)
        self.assertEqual(updated_driver.data["license_number"], "ABC-123")
        self.assertEqual(updated_driver.data["vehicle_id"], vehicle.data["id"])
        self.assertEqual(updated_driver.data["vehicle_name"], "Yuk mashinasi")
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin,
            entity_type="DriverProfile",
            entity_id=str(driver.pk),
            action="update",
        ).exists())

        other_vehicle = Vehicle.objects.create(
            company=self.other_company,
            name="B transporti",
            plate_number="01B200AA",
            capacity=Decimal("100.00"),
        )
        denied_assignment = self.client.patch(
            f"/api/v1/admin/drivers/{driver.pk}/",
            {"vehicle_id": other_vehicle.pk},
            format="json",
        )
        self.assertEqual(denied_assignment.status_code, 400)
        driver.refresh_from_db()
        self.assertEqual(driver.vehicle_id, vehicle.data["id"])

        archived_vehicle = self.client.delete(f"/api/v1/admin/vehicles/{vehicle.data['id']}/")
        self.assertEqual(archived_vehicle.status_code, 204)
        vehicle_row = Vehicle.objects.get(pk=vehicle.data["id"])
        self.assertTrue(vehicle_row.is_archived)
        self.assertFalse(vehicle_row.is_active)

        deactivated_driver = self.client.delete(f"/api/v1/admin/drivers/{driver.pk}/")
        self.assertEqual(deactivated_driver.status_code, 204)
        driver_user.refresh_from_db()
        self.assertFalse(driver_user.is_active)
        reactivated_driver = self.client.post(
            f"/api/v1/admin/drivers/{driver.pk}/activate/", {}, format="json"
        )
        self.assertEqual(reactivated_driver.status_code, 200)
        driver_user.refresh_from_db()
        self.assertTrue(driver_user.is_active)

        self.assertTrue(CompanyShopLink.objects.filter(
            company=self.company, shop=self.shop, is_active=True
        ).exists())
        shop_list = self.client.get("/api/v1/admin/shops/")
        self.assertEqual(shop_list.status_code, 200)
        self.assertEqual(
            [row["id"] for row in shop_list.data["results"]],
            [self.shop.pk],
            f"company={self.admin.company_id}, link={CompanyShopLink.objects.get(shop=self.shop).company_id}, data={shop_list.data}",
        )
        updated_shop = self.client.patch(
            f"/api/v1/admin/shops/{self.shop.pk}/",
            {"credit_limit": "7500.00"},
            format="json",
        )
        self.assertEqual(updated_shop.status_code, 200, updated_shop.data)
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).credit_limit,
            Decimal("7500.00"),
        )

        new_owner = User.objects.create_user(
            phone="+998900004031", role=User.Role.SHOP_OWNER
        )
        created_shop = self.client.post(
            "/api/v1/admin/shops/",
            {
                "owner_id": new_owner.pk,
                "name": "Yangi do‘kon",
                "phone_primary": "+998900004032",
                "address": "Markaz",
                "district": "Guliston",
                "latitude": "40.840000",
                "longitude": "68.660000",
                "credit_limit": "10000.00",
            },
            format="json",
        )
        self.assertEqual(created_shop.status_code, 201, created_shop.data)
        created_shop_row = Shop.objects.get(pk=created_shop.data["id"])
        self.assertTrue(CompanyShopLink.objects.filter(
            company=self.company, shop=created_shop_row, is_active=True
        ).exists())
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=created_shop_row).credit_limit,
            Decimal("10000.00"),
        )

        archived = self.client.post(
            f"/api/v1/admin/shops/{self.shop.pk}/archive/", {}, format="json"
        )
        self.assertEqual(archived.status_code, 200)
        self.assertFalse(CompanyShopLink.objects.get(shop=self.shop, company=self.company).is_active)

    def test_archived_shop_can_be_restored_without_changing_orders_or_financial_data(self):
        order = self.make_order()
        payment = Payment.objects.create(
            company=self.company,
            shop=self.shop,
            amount=Decimal("250.00"),
            method=Payment.Method.CASH,
        )
        entry = BalanceEntry.objects.create(
            company=self.company,
            shop=self.shop,
            amount=Decimal("250.00"),
            direction=BalanceEntry.Direction.CREDIT,
            payment=payment,
            posted_at=timezone.now(),
        )
        balance = ShopBalance.objects.get(company=self.company, shop=self.shop)
        balance.current_balance = Decimal("1750.00")
        balance.save(update_fields=("current_balance", "updated_at"))
        order_snapshot = (order.status, order.total_price, order.items.count())
        financial_snapshot = (
            balance.current_balance,
            Payment.objects.filter(shop=self.shop).count(),
            BalanceEntry.objects.filter(shop=self.shop).count(),
            payment.amount,
            entry.amount,
        )

        archived = self.client.post(
            f"/api/v1/admin/shops/{self.shop.pk}/archive/", {}, format="json"
        )
        self.assertEqual(archived.status_code, 200, archived.data)
        archived_shops = self.client.get(
            "/api/v1/admin/shops/", {"status": "all", "page_size": 100}
        )
        self.assertEqual(archived_shops.status_code, 200, archived_shops.data)
        archived_row = next(
            row for row in archived_shops.data["results"] if row["id"] == self.shop.pk
        )
        self.assertEqual(archived_row["status"], Shop.Status.ARCHIVED)

        restored = self.client.post(
            f"/api/v1/admin/shops/{self.shop.pk}/restore/", {}, format="json"
        )
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertEqual(restored.data["status"], Shop.Status.ACTIVE)
        self.assertTrue(CompanyShopLink.objects.get(
            company=self.company, shop=self.shop
        ).is_active)
        self.shop.refresh_from_db()
        order.refresh_from_db()
        balance.refresh_from_db()
        payment.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(order_snapshot, (order.status, order.total_price, order.items.count()))
        self.assertEqual(financial_snapshot, (
            balance.current_balance,
            Payment.objects.filter(shop=self.shop).count(),
            BalanceEntry.objects.filter(shop=self.shop).count(),
            payment.amount,
            entry.amount,
        ))
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin,
            entity_type="Shop",
            entity_id=str(self.shop.pk),
            action="restore",
        ).exists())

        self.client.force_authenticate(self.owner)
        catalog = self.client.get("/api/v1/catalog/")
        self.assertEqual(catalog.status_code, 200, catalog.data)
        self.assertEqual([row["id"] for row in catalog.data["results"]], [self.product.pk])

    def test_company_admin_cannot_restore_another_company_shop(self):
        self.client.post(
            f"/api/v1/admin/shops/{self.shop.pk}/archive/", {}, format="json"
        )
        self.client.force_authenticate(self.other_admin)

        response = self.client.post(
            f"/api/v1/admin/shops/{self.shop.pk}/restore/", {}, format="json"
        )

        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(CompanyShopLink.objects.get(
            company=self.company, shop=self.shop
        ).is_active)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.status, Shop.Status.ARCHIVED)

    def test_staff_creation_cannot_assign_super_admin_or_other_company(self):
        response = self.client.post(
            "/api/v1/admin/staff/",
            {
                "phone": "+998900004010",
                "role": User.Role.DRIVER,
                "password": "temporary-password",
                "company_id": self.other_company.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        driver = User.objects.get(phone="+998900004010")
        self.assertEqual(driver.company, self.company)
        self.assertTrue(DriverProfile.objects.filter(user=driver, company=self.company).exists())
        deactivated = self.client.post(
            f"/api/v1/admin/staff/{driver.pk}/deactivate/", {}, format="json"
        )
        self.assertEqual(deactivated.status_code, 200)
        driver.refresh_from_db()
        self.assertFalse(driver.is_active)
        self.assertTrue(driver.is_blocked)

        denied = self.client.post(
            "/api/v1/admin/staff/",
            {
                "phone": "+998900004011",
                "role": User.Role.SUPER_ADMIN,
                "password": "temporary-password",
            },
            format="json",
        )
        self.assertEqual(denied.status_code, 400)

    def test_staff_admin_can_edit_reset_password_and_deactivate_company_staff(self):
        created = self.client.post(
            "/api/v1/admin/staff/",
            {
                "phone": "+998900004012",
                "role": User.Role.COMPANY_ADMIN,
                "password": "temporary-password",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        staff = User.objects.get(pk=created.data["id"])
        old_auth_version = staff.auth_version

        edited = self.client.patch(
            f"/api/v1/admin/staff/{staff.pk}/",
            {"phone": "+998900004013"},
            format="json",
        )
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertEqual(edited.data["phone"], "+998900004013")
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin, entity_type="User", entity_id=str(staff.pk), action="update"
        ).exists())

        mismatch = self.client.post(
            f"/api/v1/admin/staff/{staff.pk}/reset-password/",
            {"password": "New-Safe-Password-939!", "password_confirm": "other-password"},
            format="json",
        )
        self.assertEqual(mismatch.status_code, 400)

        reset = self.client.post(
            f"/api/v1/admin/staff/{staff.pk}/reset-password/",
            {
                "password": "New-Safe-Password-939!",
                "password_confirm": "New-Safe-Password-939!",
            },
            format="json",
        )
        self.assertEqual(reset.status_code, 200, reset.data)
        staff.refresh_from_db()
        self.assertTrue(staff.check_password("New-Safe-Password-939!"))
        self.assertGreater(staff.auth_version, old_auth_version)
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin,
            entity_type="User",
            entity_id=str(staff.pk),
            action="reset_password",
        ).exists())

        deactivated = self.client.post(
            f"/api/v1/admin/staff/{staff.pk}/deactivate/", {}, format="json"
        )
        self.assertEqual(deactivated.status_code, 200)
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)
        self.assertTrue(staff.is_blocked)

        self_deactivation = self.client.post(
            f"/api/v1/admin/staff/{self.admin.pk}/deactivate/", {}, format="json"
        )
        self.assertEqual(self_deactivation.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self_update = self.client.patch(
            f"/api/v1/admin/staff/{self.admin.pk}/",
            {"phone": "+998900004019"},
            format="json",
        )
        self.assertEqual(self_update.status_code, 400)
        self_password_reset = self.client.post(
            f"/api/v1/admin/staff/{self.admin.pk}/reset-password/",
            {
                "password": "New-Safe-Password-939!",
                "password_confirm": "New-Safe-Password-939!",
            },
            format="json",
        )
        self.assertEqual(self_password_reset.status_code, 400)

    def test_staff_management_rejects_other_company_ids_and_ordinary_staff(self):
        for method, path, data in (
            ("patch", f"/api/v1/admin/staff/{self.other_admin.pk}/", {"phone": "+998900004015"}),
            (
                "post",
                f"/api/v1/admin/staff/{self.other_admin.pk}/reset-password/",
                {"password": "New-Safe-Password-939!", "password_confirm": "New-Safe-Password-939!"},
            ),
            ("post", f"/api/v1/admin/staff/{self.other_admin.pk}/deactivate/", {}),
        ):
            response = getattr(self.client, method)(path, data, format="json")
            self.assertEqual(response.status_code, 404, response.data)

        ordinary_employee = User.objects.create_user(
            phone="+998900004016",
            password="temporary-password",
            company=self.company,
            role=User.Role.DRIVER,
        )
        self.client.force_authenticate(ordinary_employee)
        for method, path, data in (
            ("get", "/api/v1/admin/staff/", None),
            (
                "post",
                "/api/v1/admin/staff/",
                {
                    "phone": "+998900004017",
                    "role": User.Role.COMPANY_ADMIN,
                    "password": "temporary-password",
                },
            ),
            ("patch", f"/api/v1/admin/staff/{ordinary_employee.pk}/", {"phone": "+998900004018"}),
            ("patch", f"/api/v1/admin/staff/{self.admin.pk}/", {"phone": "+998900004018"}),
            (
                "post",
                f"/api/v1/admin/staff/{ordinary_employee.pk}/reset-password/",
                {"password": "New-Safe-Password-939!", "password_confirm": "New-Safe-Password-939!"},
            ),
            (
                "post",
                f"/api/v1/admin/staff/{self.admin.pk}/reset-password/",
                {"password": "New-Safe-Password-939!", "password_confirm": "New-Safe-Password-939!"},
            ),
            ("post", f"/api/v1/admin/staff/{ordinary_employee.pk}/deactivate/", {}),
        ):
            response = (
                getattr(self.client, method)(path)
                if data is None
                else getattr(self.client, method)(path, data, format="json")
            )
            self.assertEqual(response.status_code, 403, response.data)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.phone, "+998900004001")
        self.assertFalse(self.admin.check_password("New-Safe-Password-939!"))

    def test_shop_owner_cannot_create_payment_and_staff_payment_updates_ledger(self):
        self.client.force_authenticate(self.owner)
        denied = self.client.post(
            "/api/v1/admin/payments/",
            {"shop_id": self.shop.pk, "amount": "500.00", "method": Payment.Method.CASH},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/admin/payments/",
            {
                "shop_id": self.shop.pk,
                "amount": "500.00",
                "method": Payment.Method.CASH,
                "paid_at": "2026-10-01",
                "note": "Naqd to‘lov",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount"], "500.00")
        self.assertTrue(response.data["paid_at"].startswith("2026-10-01"))
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("-500.00"),
        )
        self.assertEqual(BalanceEntry.objects.filter(payment_id=response.data["id"]).count(), 1)
        balances = self.client.get("/api/v1/admin/balances/")
        self.assertEqual(balances.status_code, 200)
        self.assertEqual(balances.data["results"][0]["current_balance"], "-500.00")
        self.assertEqual(len(balances.data["results"][0]["entries"]), 1)
        self.assertEqual(balances.data["results"][0]["last_payment_at"], "2026-10-01")

        self.client.force_authenticate(self.owner)
        finance = self.client.get("/api/v1/shop/finance/")
        self.assertEqual(finance.status_code, 200)
        self.assertEqual(len(finance.data["entries"]), 1)
        self.assertEqual(finance.data["payments"][0]["amount"], "500.00")

    def test_balance_adjustments_are_company_scoped_and_keep_reverse_entries(self):
        container = ReturnableContainer.objects.create(
            company=self.company,
            name="Qaytariladigan idish",
            deposit_amount=Decimal("250.00"),
        )
        ContainerMovement.objects.create(
            company=self.company,
            shop=self.shop,
            container=container,
            quantity_delta=Decimal("2.00"),
        )
        self.client.force_authenticate(self.other_admin)
        ShopBalance.objects.create(company=self.other_company, shop=self.other_shop)
        other_balances = self.client.get("/api/v1/admin/balances/")
        self.assertEqual(
            [row["shop_id"] for row in other_balances.data["results"]],
            [self.other_shop.pk],
        )
        self.assertEqual(str(other_balances.data["results"][0]["container_deposit"]), "0.00")
        foreign_adjustment = self.client.post(
            "/api/v1/admin/balances/adjust/",
            {
                "shop_id": self.shop.pk,
                "amount": "500.00",
                "direction": BalanceEntry.Direction.DEBIT,
                "note": "Boshqa kompaniya yozuvi",
            },
            format="json",
        )
        self.assertEqual(foreign_adjustment.status_code, 404)
        self.assertFalse(BalanceEntry.objects.filter(shop=self.shop).exists())

        self.client.force_authenticate(self.admin)
        own_balances = self.client.get("/api/v1/admin/balances/")
        self.assertEqual(len(own_balances.data["results"]), 1)
        self.assertEqual(own_balances.data["results"][0]["container_deposit"], "500.00")
        for direction, amount, note in (
            (BalanceEntry.Direction.DEBIT, "1000.00", "Qarz xatosi"),
            (BalanceEntry.Direction.CREDIT, "1000.00", "Qarz xatosini qaytarish"),
        ):
            response = self.client.post(
                "/api/v1/admin/balances/adjust/",
                {
                    "shop_id": self.shop.pk,
                    "amount": amount,
                    "direction": direction,
                    "note": note,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertIsNotNone(response.data["posted_at"])

        entries = BalanceEntry.objects.filter(shop=self.shop).order_by("pk")
        self.assertEqual(entries.count(), 2)
        self.assertEqual(
            list(entries.values_list("direction", flat=True)),
            [BalanceEntry.Direction.DEBIT, BalanceEntry.Direction.CREDIT],
        )
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("0.00"),
        )
        self.client.force_authenticate(self.owner)
        shop_finance = self.client.get("/api/v1/shop/finance/")
        self.assertEqual(shop_finance.status_code, 200)
        self.assertEqual(shop_finance.data["balances"][0]["container_deposit"], "500.00")
        denied_adjustment = self.client.post(
            "/api/v1/admin/balances/adjust/",
            {
                "shop_id": self.shop.pk,
                "amount": "100.00",
                "direction": BalanceEntry.Direction.DEBIT,
                "note": "Do‘kon egasi tuzatishi",
            },
            format="json",
        )
        self.assertEqual(denied_adjustment.status_code, 403)

    def test_driver_can_only_record_payment_for_shop_on_own_trip(self):
        driver_user = User.objects.create_user(
            phone="+998900004020",
            password="driver-password",
            company=self.company,
            role=User.Role.DRIVER,
        )
        driver = DriverProfile.objects.create(company=self.company, user=driver_user)
        vehicle = Vehicle.objects.create(
            company=self.company, name="V1", plate_number="01A100AA", capacity=100
        )
        trip = Trip.objects.create(
            company=self.company, date=timezone.localdate(), vehicle=vehicle, driver=driver
        )
        TripStop.objects.create(company=self.company, trip=trip, shop=self.shop, sequence=1)
        self.client.force_authenticate(driver_user)

        response = self.client.post(
            "/api/v1/admin/payments/",
            {
                "shop_id": self.shop.pk,
                "amount": "100.00",
                "method": Payment.Method.CASH,
                "trip_id": trip.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        forbidden = self.client.post(
            "/api/v1/admin/payments/",
            {
                "shop_id": self.other_shop.pk,
                "amount": "100.00",
                "method": Payment.Method.CASH,
                "trip_id": trip.pk,
            },
            format="json",
        )
        self.assertEqual(forbidden.status_code, 404)
