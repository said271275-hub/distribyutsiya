from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.logistics.models import DriverProfile, Trip, TripStop, TripStopOrder, Vehicle
from apps.logistics.routing import nearest_neighbor_order
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import BalanceEntry, ShopBalance


class TripApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Kompaniya A",
            stop_duration_minutes=20,
            average_route_speed_kph=30,
        )
        cls.other_company = Company.objects.create(name="Kompaniya B")
        cls.admin = User.objects.create_user(
            phone="+998901110001",
            company=cls.company,
            role=User.Role.COMPANY_ADMIN,
        )
        cls.other_admin = User.objects.create_user(
            phone="+998901110002",
            company=cls.other_company,
            role=User.Role.COMPANY_ADMIN,
        )
        cls.driver_user = User.objects.create_user(
            phone="+998901110003",
            company=cls.company,
            role=User.Role.DRIVER,
        )
        cls.other_driver_user = User.objects.create_user(
            phone="+998901110004",
            company=cls.other_company,
            role=User.Role.DRIVER,
        )
        cls.driver = DriverProfile.objects.create(
            company=cls.company, user=cls.driver_user
        )
        cls.other_driver = DriverProfile.objects.create(
            company=cls.other_company, user=cls.other_driver_user
        )
        cls.vehicle = Vehicle.objects.create(
            company=cls.company,
            name="Yuk mashinasi",
            plate_number="01A400AA",
            capacity=Decimal("50.00"),
        )
        cls.other_vehicle = Vehicle.objects.create(
            company=cls.other_company,
            name="B mashinasi",
            plate_number="01B400AA",
            capacity=Decimal("50.00"),
        )
        cls.product = Product.objects.create(
            company=cls.company,
            name="Suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
            unit_weight=Decimal("10.000"),
            unit_volume=Decimal("2.000"),
        )
        cls.shop = cls.make_shop(
            owner_phone="+998901110010",
            shop_phone="+998901110020",
            name="Markaz do‘koni",
            latitude="40.840000",
            longitude="68.660000",
            company=cls.company,
        )
        cls.nearby_shop = cls.make_shop(
            owner_phone="+998901110011",
            shop_phone="+998901110021",
            name="Yaqin do‘kon",
            latitude="40.850000",
            longitude="68.660000",
            company=cls.company,
        )
        cls.far_shop = cls.make_shop(
            owner_phone="+998901110012",
            shop_phone="+998901110022",
            name="Uzoq do‘kon",
            latitude="41.500000",
            longitude="68.660000",
            company=cls.company,
        )
        cls.other_shop = cls.make_shop(
            owner_phone="+998901110013",
            shop_phone="+998901110023",
            name="B do‘koni",
            latitude="40.840000",
            longitude="68.660000",
            company=cls.other_company,
        )

    @classmethod
    def make_shop(
        cls, *, owner_phone, shop_phone, name, latitude, longitude, company
    ):
        owner = User.objects.create_user(
            phone=owner_phone, role=User.Role.SHOP_OWNER
        )
        shop = Shop.objects.create(
            owner=owner,
            name=name,
            phone_primary=shop_phone,
            address="Markaz",
            district="Guliston",
            latitude=Decimal(latitude),
            longitude=Decimal(longitude),
        )
        CompanyShopLink.objects.create(company=company, shop=shop)
        return shop

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def make_order(
        self,
        *,
        shop=None,
        quantity="1.00",
        delivery_date=None,
        order_status=Order.Status.CONFIRMED,
    ):
        order = Order.objects.create(
            company=self.company,
            shop=shop or self.shop,
            status=order_status,
            delivery_date=delivery_date or date.today(),
        )
        OrderItem.objects.create(
            company=self.company,
            order=order,
            product=self.product,
            quantity=Decimal(quantity),
            unit_price=Decimal("1000.00"),
        )
        order.recalculate_total()
        return order

    def create_trip(self, *, delivery_date=None):
        response = self.client.post(
            "/api/v1/admin/trips/",
            {
                "date": (delivery_date or date.today()).isoformat(),
                "vehicle_id": self.vehicle.pk,
                "driver_id": self.driver.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return Trip.objects.get(pk=response.data["id"])

    def add_stop(self, trip, shop, order_ids):
        return self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/stops/",
            {"shop_id": shop.pk, "order_ids": order_ids},
            format="json",
        )

    def test_trip_create_rejects_foreign_company_vehicle(self):
        response = self.client.post(
            "/api/v1/admin/trips/",
            {
                "date": date.today().isoformat(),
                "vehicle_id": self.other_vehicle.pk,
                "driver_id": self.driver.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_suggestion_combines_orders_for_same_shop_and_splits_at_capacity(self):
        self.vehicle.capacity = Decimal("25.00")
        self.vehicle.save(update_fields=("capacity", "updated_at"))
        vehicle_ids = [self.vehicle.pk]
        for index in range(2):
            vehicle = Vehicle.objects.create(
                company=self.company,
                name=f"Qo‘shimcha yuk mashinasi {index + 1}",
                plate_number=f"01A40{index + 1}AA",
                capacity=Decimal("25.00"),
            )
            vehicle_ids.append(vehicle.pk)
            driver_user = User.objects.create_user(
                phone=f"+9989011100{16 + index}",
                company=self.company,
                role=User.Role.DRIVER,
            )
            DriverProfile.objects.create(company=self.company, user=driver_user)
        delivery_date = date.today() + timedelta(days=1)
        first = self.make_order(
            quantity="1.00", delivery_date=delivery_date
        )
        second = self.make_order(
            quantity="1.00", delivery_date=delivery_date
        )
        nearby = self.make_order(
            shop=self.nearby_shop,
            quantity="1.00",
            delivery_date=delivery_date,
        )
        far = self.make_order(
            shop=self.far_shop,
            quantity="1.00",
            delivery_date=delivery_date,
        )

        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": delivery_date.isoformat(), "vehicle_ids": vehicle_ids},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        trips = response.data["trips"]
        self.assertGreaterEqual(len(trips), 2)
        self.assertEqual(len({trip["vehicle_id"] for trip in trips}), len(trips))
        self.assertEqual(len({trip["driver_id"] for trip in trips}), len(trips))
        self.assertTrue(any(trip["split_for_capacity"] for trip in trips))
        self.assertEqual(
            sorted(order_id for trip in trips for order_id in trip["order_ids"]),
            sorted((first.pk, second.pk, nearby.pk, far.pk)),
        )
        same_shop_stop = next(
            stop
            for trip in trips
            for stop in trip["stops"]
            if stop["shop_id"] == self.shop.pk
        )
        self.assertEqual(same_shop_stop["order_ids"], [first.pk, second.pk])

    def test_suggestion_flags_single_shop_over_capacity(self):
        self.vehicle.capacity = Decimal("5.00")
        self.vehicle.save(update_fields=("capacity", "updated_at"))
        delivery_date = date.today() + timedelta(days=1)
        order = self.make_order(quantity="1.00", delivery_date=delivery_date)

        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": delivery_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["trips"][0]["order_ids"], [order.pk])
        self.assertTrue(response.data["trips"][0]["capacity_exceeded"])
        self.assertTrue(response.data["trips"][0]["warning"])

    def test_suggestion_does_not_reuse_two_vehicles_or_drivers_for_third_trip(self):
        delivery_date = date.today() + timedelta(days=1)
        self.vehicle.capacity = Decimal("10.00")
        self.vehicle.save(update_fields=("capacity", "updated_at"))
        second_vehicle = Vehicle.objects.create(
            company=self.company,
            name="Ikkinchi yuk mashinasi",
            plate_number="01A401AA",
            capacity=Decimal("10.00"),
        )
        second_driver_user = User.objects.create_user(
            phone="+998901110005",
            company=self.company,
            role=User.Role.DRIVER,
        )
        DriverProfile.objects.create(
            company=self.company, user=second_driver_user
        )
        orders = [
            self.make_order(shop=self.shop, delivery_date=delivery_date),
            self.make_order(shop=self.nearby_shop, delivery_date=delivery_date),
            self.make_order(shop=self.far_shop, delivery_date=delivery_date),
        ]

        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {
                "date": delivery_date.isoformat(),
                "vehicle_ids": [self.vehicle.pk, second_vehicle.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        trips = response.data["trips"]
        self.assertEqual(len(trips), 2)
        self.assertEqual(
            len({trip["vehicle_id"] for trip in trips}),
            len(trips),
        )
        self.assertEqual(
            len({trip["driver_id"] for trip in trips}),
            len(trips),
        )
        unassigned = response.data["unassigned_orders"]
        self.assertEqual(
            [item["order_id"] for item in unassigned],
            [orders[2].pk],
        )
        self.assertIn("mashina yetmadi", unassigned[0]["reason"])
        assigned_ids = [
            order_id for trip in trips for order_id in trip["order_ids"]
        ]
        self.assertEqual(
            sorted(assigned_ids + [item["order_id"] for item in unassigned]),
            sorted(order.pk for order in orders),
        )

    def test_capacity_uses_one_metric_for_all_suggested_stops(self):
        delivery_date = date.today() + timedelta(days=1)
        self.vehicle.volume_capacity = Decimal("1.00")
        self.vehicle.save(update_fields=("volume_capacity", "updated_at"))
        second_vehicle = Vehicle.objects.create(
            company=self.company,
            name="Hajm bo‘yicha ikkinchi yuk mashinasi",
            plate_number="01A403AA",
            capacity=Decimal("50.00"),
            volume_capacity=Decimal("1.00"),
        )
        second_driver_user = User.objects.create_user(
            phone="+998901110098",
            company=self.company,
            role=User.Role.DRIVER,
        )
        DriverProfile.objects.create(company=self.company, user=second_driver_user)
        no_weight_product = Product.objects.create(
            company=self.company,
            name="Og‘irligi ko‘rsatilmagan suv",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
            unit_volume=Decimal("3.000"),
        )
        first = self.make_order(delivery_date=delivery_date)
        second = self.make_order(
            shop=self.nearby_shop, delivery_date=delivery_date
        )
        OrderItem.objects.filter(order=second).update(product=no_weight_product)

        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": delivery_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        suggestions = response.data["trips"]
        self.assertEqual(len(suggestions), 2)
        for suggestion in suggestions:
            self.assertEqual(suggestion["capacity_metric"], "volume")
            self.assertEqual(suggestion["vehicle_capacity"], Decimal("1.00"))
            self.assertTrue(suggestion["capacity_exceeded"])
            self.assertTrue(
                all(stop["capacity_metric"] == "volume" for stop in suggestion["stops"])
            )
        self.assertEqual(
            sorted(order_id for trip in suggestions for order_id in trip["order_ids"]),
            sorted((first.pk, second.pk)),
        )

    def test_suggestion_pairs_assigned_driver_with_its_vehicle(self):
        delivery_date = date.today() + timedelta(days=1)
        self.vehicle.capacity = Decimal("15.00")
        self.vehicle.save(update_fields=("capacity", "updated_at"))
        self.driver.vehicle = self.vehicle
        self.driver.save(update_fields=("vehicle", "updated_at"))
        second_vehicle = Vehicle.objects.create(
            company=self.company,
            name="Ikkinchi yuk mashinasi",
            plate_number="01A402AA",
            capacity=Decimal("15.00"),
        )
        unassigned_driver_user = User.objects.create_user(
            phone="+998901110099",
            company=self.company,
            role=User.Role.DRIVER,
        )
        unassigned_driver = DriverProfile.objects.create(
            company=self.company,
            user=unassigned_driver_user,
        )
        self.make_order(shop=self.shop, delivery_date=delivery_date)
        self.make_order(shop=self.nearby_shop, delivery_date=delivery_date)

        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": delivery_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        trips = response.data["trips"]
        self.assertEqual(len(trips), 2)
        self.assertEqual(
            {trip["vehicle_id"]: trip["driver_id"] for trip in trips},
            {
                self.vehicle.pk: self.driver.pk,
                second_vehicle.pk: unassigned_driver.pk,
            },
        )

    def test_volume_suggestion_warns_when_vehicle_volume_capacity_is_missing(self):
        delivery_date = date.today() + timedelta(days=1)
        product = Product.objects.create(
            company=self.company,
            name="Hajmi bor, og‘irligi yo‘q mahsulot",
            unit=Product.Unit.BOX,
            price=Decimal("1000.00"),
            unit_volume=Decimal("2.000"),
        )
        order = self.make_order(delivery_date=delivery_date)
        order.items.update(product=product)

        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": delivery_date.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        suggestion = response.data["trips"][0]
        self.assertEqual(suggestion["capacity_metric"], "volume")
        self.assertIsNone(suggestion["vehicle_capacity"])
        self.assertIn("sig‘im kiritilmagan", suggestion["warning"])
        self.assertEqual(suggestion["order_ids"], [order.pk])

    def test_empty_day_returns_empty_suggestions(self):
        response = self.client.post(
            "/api/v1/admin/trips/suggest/",
            {"date": (date.today() + timedelta(days=20)).isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["trips"], [])
        self.assertEqual(response.data["unassigned_order_ids"], [])

    def test_same_stop_can_hold_multiple_orders_and_confirm_updates_status_and_eta(self):
        order_a = self.make_order(order_status=Order.Status.NEW)
        order_b = self.make_order(order_status=Order.Status.NEW)
        trip = self.create_trip()
        stop_response = self.add_stop(trip, self.shop, [order_a.pk, order_b.pk])
        self.assertEqual(stop_response.status_code, 201, stop_response.data)
        stop = TripStop.objects.get(trip=trip)
        self.assertEqual(
            set(stop.order_links.values_list("order_id", flat=True)),
            {order_a.pk, order_b.pk},
        )

        confirmed = self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/confirm/",
            {"reason": "Reys tasdiqlandi"},
            format="json",
        )

        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.Status.CONFIRMED)
        self.assertEqual(confirmed.data["routing_source"], Trip.RoutingSource.FALLBACK)
        stop.refresh_from_db()
        self.assertIsNotNone(stop.eta)
        self.assertEqual(
            stop.eta_window_to - stop.eta_window_from,
            timedelta(minutes=90),
        )
        self.assertEqual(stop.eta_window_from, stop.eta - timedelta(minutes=45))
        for order in (order_a, order_b):
            order.refresh_from_db()
            self.assertEqual(order.status, Order.Status.CONFIRMED)
            self.assertTrue(OrderStatusHistory.objects.filter(
                order=order, actor=self.admin, status=Order.Status.CONFIRMED
            ).exists())
            self.assertFalse(BalanceEntry.objects.filter(order=order).exists())
        self.assertTrue(AuditLog.objects.filter(
            actor=self.admin, action="trip.confirm", entity_id=str(trip.pk)
        ).exists())

    def test_confirmed_trip_eta_is_exposed_to_shop_owner_order_api(self):
        order = self.make_order(order_status=Order.Status.NEW)
        trip = self.create_trip()
        self.assertEqual(self.add_stop(trip, self.shop, [order.pk]).status_code, 201)
        response = self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/confirm/",
            {"reason": "Tasdiq"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(self.shop.owner)
        shop_response = self.client.get(f"/api/v1/orders/{order.pk}/")

        self.assertEqual(shop_response.status_code, 200, shop_response.data)
        self.assertIsNotNone(shop_response.data["eta"])
        self.assertIsNotNone(shop_response.data["eta_window_from"])
        self.assertIsNotNone(shop_response.data["eta_window_to"])
        shop_list_response = self.client.get("/api/v1/orders/")
        self.assertEqual(shop_list_response.status_code, 200, shop_list_response.data)
        listed_order = next(
            item for item in shop_list_response.data["results"]
            if item["id"] == order.pk
        )
        self.assertEqual(listed_order["eta"], shop_response.data["eta"])
        self.assertEqual(
            listed_order["eta_window_from"],
            shop_response.data["eta_window_from"],
        )

    def test_stop_reorder_remove_and_cancel_leave_orders_ready_to_reassign(self):
        order_a = self.make_order(shop=self.shop)
        order_b = self.make_order(shop=self.nearby_shop)
        trip = self.create_trip()
        self.assertEqual(self.add_stop(trip, self.shop, [order_a.pk]).status_code, 201)
        self.assertEqual(
            self.add_stop(trip, self.nearby_shop, [order_b.pk]).status_code, 201
        )
        stops = list(trip.stops.order_by("sequence"))
        reordered = self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/stops/reorder/",
            {"stop_ids": [stops[1].pk, stops[0].pk]},
            format="json",
        )
        self.assertEqual(reordered.status_code, 200, reordered.data)
        self.assertEqual(
            list(trip.stops.order_by("sequence").values_list("id", flat=True)),
            [stops[1].pk, stops[0].pk],
        )
        removed = self.client.delete(
            f"/api/v1/admin/trips/{trip.pk}/stops/{stops[0].pk}/"
        )
        self.assertEqual(removed.status_code, 204)

        cancelled = self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/cancel/",
            {"reason": "Boshqa reysga ko‘chirish"},
            format="json",
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.Status.CANCELLED)
        self.assertFalse(trip.stops.exists())
        self.assertEqual(Order.objects.get(pk=order_a.pk).status, Order.Status.CONFIRMED)
        self.assertEqual(Order.objects.get(pk=order_b.pk).status, Order.Status.CONFIRMED)

    def test_driver_only_reads_own_trips_and_company_admin_cannot_read_other_company(self):
        trip = self.create_trip()
        own = self.client.get(f"/api/v1/admin/trips/{trip.pk}/")
        self.assertEqual(own.status_code, 200)

        self.client.force_authenticate(self.other_admin)
        self.assertEqual(self.client.get(f"/api/v1/admin/trips/{trip.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/admin/trips/").data["count"], 0)

        self.client.force_authenticate(self.driver_user)
        driver_trips = self.client.get("/api/v1/driver/trips/")
        self.assertEqual(driver_trips.status_code, 200)
        self.assertEqual([row["id"] for row in driver_trips.data], [trip.pk])
        self.assertEqual(
            self.client.post("/api/v1/admin/trips/", {}, format="json").status_code,
            403,
        )

        self.client.force_authenticate(self.other_driver_user)
        self.assertEqual(self.client.get("/api/v1/driver/trips/").data, [])

    def test_driver_trips_include_stop_details_load_list_and_are_scoped_by_driver_company_and_date(self):
        trip_date = timezone.localdate()
        own_trip = self.create_trip(delivery_date=trip_date)
        order = self.make_order(shop=self.shop, quantity="3.00", delivery_date=trip_date)
        self.add_stop(own_trip, self.shop, [order.pk])

        other_same_company_user = User.objects.create_user(
            phone="+998901110005",
            company=self.company,
            role=User.Role.DRIVER,
        )
        other_same_company_driver = DriverProfile.objects.create(
            company=self.company, user=other_same_company_user
        )
        same_company_trip = Trip.objects.create(
            company=self.company,
            date=trip_date,
            vehicle=self.vehicle,
            driver=other_same_company_driver,
        )
        TripStop.objects.create(
            company=self.company,
            trip=same_company_trip,
            shop=self.nearby_shop,
            sequence=1,
        )
        foreign_trip = Trip.objects.create(
            company=self.other_company,
            date=trip_date,
            vehicle=self.other_vehicle,
            driver=self.other_driver,
        )
        TripStop.objects.create(
            company=self.other_company,
            trip=foreign_trip,
            shop=self.other_shop,
            sequence=1,
        )
        future_trip = self.create_trip(delivery_date=trip_date + timedelta(days=1))

        self.client.force_authenticate(self.driver_user)
        response = self.client.get(
            "/api/v1/driver/trips/",
            {"date": trip_date.isoformat()},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["id"] for row in response.data], [own_trip.pk])
        trip_data = response.data[0]
        self.assertEqual(trip_data["vehicle_name"], self.vehicle.name)
        self.assertEqual(trip_data["vehicle_plate_number"], self.vehicle.plate_number)
        self.assertEqual(trip_data["stops"][0]["shop_name"], self.shop.name)
        self.assertEqual(trip_data["stops"][0]["address"], self.shop.address)
        self.assertEqual(trip_data["stops"][0]["phone"], self.shop.phone_primary)
        self.assertEqual(trip_data["stops"][0]["orders"][0]["id"], order.pk)
        self.assertEqual(
            trip_data["stops"][0]["orders"][0]["items"][0]["product_name"],
            self.product.name,
        )
        self.assertEqual(
            trip_data["picking_list"],
            [{"product_name": self.product.name, "unit": self.product.unit, "quantity": "3.00"}],
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/driver/trips/",
                {"date": (trip_date + timedelta(days=1)).isoformat()},
            ).data[0]["id"],
            future_trip.pk,
        )
        self.assertEqual(
            self.client.get("/api/v1/driver/trips/", {"date": "not-a-date"}).status_code,
            400,
        )
        self.client.force_authenticate(other_same_company_user)
        self.assertEqual(
            self.client.get(
                "/api/v1/driver/trips/",
                {"date": trip_date.isoformat()},
            ).data[0]["id"],
            same_company_trip.pk,
        )

    def test_driver_can_only_mark_stops_on_own_trip(self):
        trip = self.create_trip()
        order = self.make_order()
        self.add_stop(trip, self.shop, [order.pk])
        self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/confirm/",
            {"reason": "Reys tasdiqlandi"},
            format="json",
        )

        other_same_company_user = User.objects.create_user(
            phone="+998901110025",
            company=self.company,
            role=User.Role.DRIVER,
        )
        other_same_company_driver = DriverProfile.objects.create(
            company=self.company, user=other_same_company_user
        )
        other_company_trip = Trip.objects.create(
            company=self.company,
            date=date.today(),
            vehicle=self.vehicle,
            driver=other_same_company_driver,
        )
        same_company_foreign_stop = TripStop.objects.create(
            company=self.company,
            trip=other_company_trip,
            shop=self.nearby_shop,
            sequence=1,
        )
        foreign_trip = Trip.objects.create(
            company=self.other_company,
            date=date.today(),
            vehicle=self.other_vehicle,
            driver=self.other_driver,
        )
        foreign_stop = TripStop.objects.create(
            company=self.other_company,
            trip=foreign_trip,
            shop=self.other_shop,
            sequence=1,
        )
        own_stop = trip.stops.get()
        self.client.force_authenticate(self.driver_user)

        paths = (
            f"/api/v1/driver/trips/{trip.pk}/stops/{same_company_foreign_stop.pk}/delivered/",
            f"/api/v1/driver/trips/{other_company_trip.pk}/stops/{same_company_foreign_stop.pk}/delivered/",
            f"/api/v1/driver/trips/{foreign_trip.pk}/stops/{foreign_stop.pk}/delivered/",
        )
        for path in paths:
            self.assertEqual(
                self.client.post(path, {}, format="json").status_code,
                404,
            )
        own_stop.refresh_from_db()
        self.assertIsNone(own_stop.delivered_at)
        self.assertIsNone(same_company_foreign_stop.delivered_at)
        self.assertIsNone(foreign_stop.delivered_at)
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.CONFIRMED)

    def test_driver_delivery_marks_all_shop_orders_once_and_updates_trip_and_shop(self):
        first_order = self.make_order()
        second_order = self.make_order()
        next_order = self.make_order(shop=self.nearby_shop)
        trip = self.create_trip()
        self.add_stop(trip, self.shop, [first_order.pk, second_order.pk])
        self.add_stop(trip, self.nearby_shop, [next_order.pk])
        confirmed = self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/confirm/",
            {"reason": "Reys tasdiqlandi"},
            format="json",
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        stops = list(trip.stops.order_by("sequence"))

        self.client.force_authenticate(self.driver_user)
        path = f"/api/v1/driver/trips/{trip.pk}/stops/{stops[0].pk}/delivered/"
        delivered = self.client.post(path, {}, format="json")
        self.assertEqual(delivered.status_code, 200, delivered.data)
        self.assertEqual(delivered.data["status"], Trip.Status.IN_PROGRESS)
        first_stop_data = delivered.data["stops"][0]
        self.assertIsNotNone(first_stop_data["delivered_at"])
        delivered_at = first_stop_data["delivered_at"]
        self.assertEqual(
            [order["id"] for order in first_stop_data["orders"]],
            [first_order.pk, second_order.pk],
        )
        for order in (first_order, second_order):
            order.refresh_from_db()
            self.assertEqual(order.status, Order.Status.DELIVERED)
            self.assertEqual(BalanceEntry.objects.filter(order=order).count(), 1)
            self.assertEqual(
                OrderStatusHistory.objects.filter(
                    order=order, status=Order.Status.DELIVERED
                ).count(),
                1,
            )

        duplicate = self.client.post(path, {}, format="json")
        self.assertEqual(duplicate.status_code, 200, duplicate.data)
        self.assertEqual(duplicate.data["stops"][0]["delivered_at"], delivered_at)
        self.assertEqual(
            BalanceEntry.objects.filter(order__in=(first_order, second_order)).count(),
            2,
        )

        self.client.force_authenticate(self.shop.owner)
        shop_order = self.client.get(f"/api/v1/orders/{first_order.pk}/")
        self.assertEqual(shop_order.status_code, 200, shop_order.data)
        self.assertEqual(shop_order.data["status"], Order.Status.DELIVERED)
        self.assertEqual(
            shop_order.data["status_history"][-1]["status"],
            Order.Status.DELIVERED,
        )

        self.client.force_authenticate(self.driver_user)
        last_delivery = self.client.post(
            f"/api/v1/driver/trips/{trip.pk}/stops/{stops[1].pk}/delivered/",
            {},
            format="json",
        )
        self.assertEqual(last_delivery.status_code, 200, last_delivery.data)
        self.assertEqual(last_delivery.data["status"], Trip.Status.COMPLETED)
        next_order.refresh_from_db()
        self.assertEqual(next_order.status, Order.Status.DELIVERED)
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("2000.00"),
        )

        self.client.force_authenticate(self.admin)
        dispatcher_trip = self.client.get(f"/api/v1/admin/trips/{trip.pk}/")
        self.assertEqual(dispatcher_trip.status_code, 200, dispatcher_trip.data)
        self.assertEqual(dispatcher_trip.data["status"], Trip.Status.COMPLETED)
        self.assertIsNotNone(dispatcher_trip.data["stops"][0]["delivered_at"])

    def test_driver_issue_is_scoped_to_own_trip_and_stop(self):
        own_trip = self.create_trip()
        own_order = self.make_order()
        self.add_stop(own_trip, self.shop, [own_order.pk])
        self.client.post(
            f"/api/v1/admin/trips/{own_trip.pk}/confirm/",
            {"reason": "Reys tasdiqlandi"},
            format="json",
        )
        another_driver_user = User.objects.create_user(
            phone="+998901110026",
            company=self.company,
            role=User.Role.DRIVER,
        )
        another_driver = DriverProfile.objects.create(
            company=self.company, user=another_driver_user
        )
        another_trip = Trip.objects.create(
            company=self.company,
            date=date.today(),
            vehicle=self.vehicle,
            driver=another_driver,
            status=Trip.Status.CONFIRMED,
        )
        foreign_stop = TripStop.objects.create(
            company=self.company,
            trip=another_trip,
            shop=self.nearby_shop,
            sequence=1,
        )
        foreign_company_trip = Trip.objects.create(
            company=self.other_company,
            date=date.today(),
            vehicle=self.other_vehicle,
            driver=self.other_driver,
            status=Trip.Status.CONFIRMED,
        )
        foreign_company_stop = TripStop.objects.create(
            company=self.other_company,
            trip=foreign_company_trip,
            shop=self.other_shop,
            sequence=1,
        )
        own_stop = own_trip.stops.get()
        self.client.force_authenticate(self.driver_user)

        paths = (
            f"/api/v1/driver/trips/{own_trip.pk}/stops/{foreign_stop.pk}/issue/",
            f"/api/v1/driver/trips/{another_trip.pk}/stops/{foreign_stop.pk}/issue/",
            f"/api/v1/driver/trips/{foreign_company_trip.pk}/stops/{foreign_company_stop.pk}/issue/",
        )
        for path in paths:
            response = self.client.post(
                path, {"reason": "shop_closed"}, format="json"
            )
            self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(AuditLog.objects.filter(action="trip.stop.issue").exists())
        own_stop.refresh_from_db()
        self.assertIsNone(own_stop.delivered_at)

    def test_driver_issue_requires_reason_and_preserves_history_for_dispatcher_and_shop(self):
        order = self.make_order()
        trip = self.create_trip()
        self.add_stop(trip, self.shop, [order.pk])
        self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/confirm/",
            {"reason": "Reys tasdiqlandi"},
            format="json",
        )
        stop = trip.stops.get()
        self.client.force_authenticate(self.driver_user)
        issue_url = f"/api/v1/driver/trips/{trip.pk}/stops/{stop.pk}/issue/"
        missing_reason = self.client.post(issue_url, {"note": "Izoh"}, format="json")
        self.assertEqual(missing_reason.status_code, 400)

        for reason, note in (
            ("shop_closed", "Eshik yopiq edi"),
            ("refused", "Qabul qilishmadi"),
        ):
            response = self.client.post(
                issue_url,
                {"reason": reason, "note": note},
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertIsNone(response.data["stops"][0]["delivered_at"])
            self.assertEqual(
                response.data["stops"][0]["issue_history"][-1]["reason"],
                reason,
            )

        self.assertEqual(
            AuditLog.objects.filter(
                action="trip.stop.issue",
                entity_type="TripStop",
                entity_id=str(stop.pk),
            ).count(),
            2,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.IN_TRANSIT)
        self.assertFalse(BalanceEntry.objects.filter(order=order).exists())

        self.client.force_authenticate(self.admin)
        dispatcher = self.client.get("/api/v1/admin/trips/")
        self.assertEqual(dispatcher.status_code, 200, dispatcher.data)
        dispatcher_stop = dispatcher.data["results"][0]["stops"][0]
        self.assertEqual(len(dispatcher_stop["issue_history"]), 2)
        self.assertEqual(dispatcher_stop["issue_history"][-1]["reason"], "refused")

        self.client.force_authenticate(self.shop.owner)
        shop_order = self.client.get(f"/api/v1/orders/{order.pk}/")
        self.assertEqual(shop_order.status_code, 200, shop_order.data)
        self.assertEqual(len(shop_order.data["delivery_issue_history"]), 2)
        self.assertEqual(shop_order.data["delivery_issue_history"][0]["reason"], "shop_closed")
        self.assertEqual(shop_order.data["driver_phone"], self.driver_user.phone)

    def test_partial_delivery_records_entered_quantity_and_uses_existing_ledger_rule(self):
        order = self.make_order(quantity="2.00")
        untouched_order = self.make_order(quantity="1.00")
        trip = self.create_trip()
        self.add_stop(trip, self.shop, [order.pk, untouched_order.pk])
        confirmed = self.client.post(
            f"/api/v1/admin/trips/{trip.pk}/confirm/",
            {"reason": "Reys tasdiqlandi"},
            format="json",
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        stop = trip.stops.get()
        item = order.items.get()
        self.client.force_authenticate(self.driver_user)
        issue_url = f"/api/v1/driver/trips/{trip.pk}/stops/{stop.pk}/issue/"

        missing_quantities = self.client.post(
            issue_url,
            {"reason": "partial_delivery"},
            format="json",
        )
        self.assertEqual(missing_quantities.status_code, 400)
        self.assertFalse(AuditLog.objects.filter(action="trip.stop.issue").exists())
        for quantity in ("2.01", "2.00"):
            invalid_quantity = self.client.post(
                issue_url,
                {
                    "reason": "partial_delivery",
                    "delivered_orders": [{
                        "order_id": order.pk,
                        "items": [{"item_id": item.pk, "quantity": quantity}],
                    }, {
                        "order_id": untouched_order.pk,
                        "items": [{
                            "item_id": untouched_order.items.get().pk,
                            "quantity": "1.00",
                        }],
                    }],
                },
                format="json",
            )
            self.assertEqual(invalid_quantity.status_code, 400, invalid_quantity.data)
            self.assertFalse(BalanceEntry.objects.filter(order=order).exists())
        self.assertFalse(AuditLog.objects.filter(action="trip.stop.issue").exists())

        response = self.client.post(
            issue_url,
            {
                "reason": "partial_delivery",
                "note": "Bir qismi qabul qilindi",
                "delivered_orders": [{
                    "order_id": order.pk,
                    "items": [{"item_id": item.pk, "quantity": "1.25"}],
                }, {
                    "order_id": untouched_order.pk,
                    "items": [{
                        "item_id": untouched_order.items.get().pk,
                        "quantity": "0.00",
                    }],
                }],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        item.refresh_from_db()
        untouched_order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(item.delivered_quantity, Decimal("1.25"))
        self.assertEqual(untouched_order.status, Order.Status.IN_TRANSIT)
        entry = BalanceEntry.objects.get(order=order)
        self.assertEqual(entry.amount, Decimal("1250.00"))
        self.assertEqual(
            ShopBalance.objects.get(company=self.company, shop=self.shop).current_balance,
            Decimal("1250.00"),
        )
        self.assertFalse(BalanceEntry.objects.filter(order=untouched_order).exists())
        self.assertIsNone(response.data["stops"][0]["delivered_at"])
        issue = response.data["stops"][0]["issue_history"][0]
        self.assertEqual(issue["reason"], "partial_delivery")
        self.assertEqual(
            issue["delivered_orders"][0]["items"][0]["quantity"],
            "1.25",
        )

        self.client.force_authenticate(self.shop.owner)
        shop_order = self.client.get(f"/api/v1/orders/{order.pk}/")
        self.assertEqual(shop_order.status_code, 200, shop_order.data)
        self.assertEqual(shop_order.data["status"], Order.Status.DELIVERED)
        self.assertEqual(shop_order.data["driver_phone"], self.driver_user.phone)
        self.assertEqual(
            shop_order.data["delivery_issue_history"][0]["delivered_items"][0]["quantity"],
            "1.25",
        )
        self.client.force_authenticate(self.driver_user)
        completed = self.client.post(
            f"/api/v1/driver/trips/{trip.pk}/stops/{stop.pk}/delivered/",
            {},
            format="json",
        )
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(completed.data["status"], Trip.Status.COMPLETED)
        untouched_order.refresh_from_db()
        self.assertEqual(untouched_order.status, Order.Status.DELIVERED)
        self.assertEqual(BalanceEntry.objects.filter(order=untouched_order).get().amount, Decimal("1000.00"))

    def test_manual_route_order_eta_and_external_osrm_failure_fallback(self):
        self.assertEqual(
            nearest_neighbor_order(
                [[0, 2, 9], [2, 0, 3], [9, 3, 0]]
            ),
            [1, 0, 2],
        )
        order_a = self.make_order(order_status=Order.Status.NEW)
        order_b = self.make_order(shop=self.nearby_shop, order_status=Order.Status.NEW)
        trip = self.create_trip()
        self.assertEqual(self.add_stop(trip, self.shop, [order_a.pk]).status_code, 201)
        self.assertEqual(
            self.add_stop(trip, self.nearby_shop, [order_b.pk]).status_code, 201
        )
        with override_settings(
            ROUTING_EXTERNAL_ENABLED=True,
            OSRM_BASE_URL="https://router.example.test",
            ROUTING_TIMEOUT_SECONDS=1,
        ):
            with patch(
                "apps.logistics.routing.urlopen",
                side_effect=URLError("offline"),
            ) as osrm:
                response = self.client.post(
                    f"/api/v1/admin/trips/{trip.pk}/confirm/",
                    {"reason": "Tasdiq"},
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["routing_source"], Trip.RoutingSource.FALLBACK)
        url = osrm.call_args.args[0]
        self.assertIn("68.66,40.84", url)
        self.assertNotIn("Markaz", url)
        self.assertNotIn("+998", url)
        stops = list(TripStop.objects.filter(trip=trip).order_by("sequence"))
        self.assertGreaterEqual(
            stops[1].eta - stops[0].eta, timedelta(minutes=20)
        )

    def test_osrm_duration_matrix_drives_route_eta(self):
        order_a = self.make_order(order_status=Order.Status.NEW)
        order_b = self.make_order(shop=self.nearby_shop, order_status=Order.Status.NEW)
        trip = self.create_trip()
        self.assertEqual(self.add_stop(trip, self.shop, [order_a.pk]).status_code, 201)
        self.assertEqual(
            self.add_stop(trip, self.nearby_shop, [order_b.pk]).status_code, 201
        )
        matrix_response = BytesIO(
            b'{"code":"Ok","distances":[[0,1000],[1000,0]],'
            b'"durations":[[0,1800],[1800,0]]}'
        )
        with override_settings(
            ROUTING_EXTERNAL_ENABLED=True,
            OSRM_BASE_URL="https://router.example.test",
            ROUTING_TIMEOUT_SECONDS=1,
        ):
            with patch(
                "apps.logistics.routing.urlopen", return_value=matrix_response
            ) as osrm:
                response = self.client.post(
                    f"/api/v1/admin/trips/{trip.pk}/route/",
                    {},
                    format="json",
                )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["routing_source"], Trip.RoutingSource.OSRM)
        stops = list(TripStop.objects.filter(trip=trip).order_by("sequence"))
        self.assertEqual(stops[1].eta - stops[0].eta, timedelta(minutes=50))
        self.assertNotIn("+998", osrm.call_args.args[0])

    def test_route_settings_and_dashboard_return_company_scoped_values(self):
        setting = self.client.patch(
            "/api/v1/admin/route-settings/",
            {"stop_duration_minutes": 30, "average_route_speed_kph": 25},
            format="json",
        )
        self.assertEqual(setting.status_code, 200, setting.data)
        self.company.refresh_from_db()
        self.assertEqual(self.company.stop_duration_minutes, 30)

        today_order = self.make_order(
            shop=self.shop, delivery_date=timezone.localdate(),
            order_status=Order.Status.DELIVERED,
        )
        pending_order = self.make_order(
            shop=self.nearby_shop, delivery_date=timezone.localdate(),
            order_status=Order.Status.CONFIRMED,
        )
        trip = self.create_trip(delivery_date=timezone.localdate())
        stop = TripStop.objects.create(
            company=self.company,
            trip=trip,
            shop=self.shop,
            sequence=1,
            eta_window_to=timezone.now() - timedelta(minutes=5),
        )
        TripStopOrder.objects.create(
            company=self.company, trip_stop=stop, order=pending_order
        )
        trip.status = Trip.Status.CONFIRMED
        trip.save(update_fields=("status", "updated_at"))
        response = self.client.get("/api/v1/admin/dashboard/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["orders_total"], 2)
        self.assertEqual(response.data["delivered"], 1)
        self.assertEqual(response.data["pending"], 1)
        self.assertEqual(response.data["total_volume"], "4.000")
        self.assertEqual(response.data["overdue_stops"], 1)
        self.assertEqual(
            response.data["trips_by_status"][Trip.Status.CONFIRMED], 1
        )

    @override_settings(DEBUG=True)
    def test_swagger_schema_lists_trip_planning_dashboard_and_driver_routes(self):
        response = self.client.get("/api/schema/")

        self.assertEqual(response.status_code, 200)
        for path in (
            "/api/v1/admin/trips/",
            "/api/v1/admin/trips/{id}/",
            "/api/v1/admin/trips/suggest/",
            "/api/v1/admin/trips/{id}/stops/",
            "/api/v1/admin/trips/{id}/stops/reorder/",
            "/api/v1/admin/trips/{id}/stops/{stop_id}/",
            "/api/v1/admin/trips/{trip_id}/stops/{stop_id}/orders/",
            "/api/v1/admin/trips/{id}/confirm/",
            "/api/v1/admin/trips/{id}/cancel/",
            "/api/v1/admin/trips/{id}/route/",
            "/api/v1/admin/dashboard/",
            "/api/v1/admin/route-settings/",
            "/api/v1/driver/trips/",
            "/api/v1/driver/trips/{trip_id}/stops/{stop_id}/delivered/",
            "/api/v1/driver/trips/{trip_id}/stops/{stop_id}/issue/",
        ):
            self.assertIn(path.encode(), response.content)
