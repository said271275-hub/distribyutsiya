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
        for suggestion in suggestions:
            self.assertEqual(suggestion["capacity_metric"], "volume")
            self.assertTrue(
                all(stop["capacity_metric"] == "volume" for stop in suggestion["stops"])
            )
        self.assertEqual(
            sorted(order_id for trip in suggestions for order_id in trip["order_ids"]),
            sorted((first.pk, second.pk)),
        )

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
            self.assertTrue(BalanceEntry.objects.filter(order=order).exists())
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
    def test_swagger_schema_lists_trip_planning_dashboard_and_driver_read_routes(self):
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
        ):
            self.assertIn(path.encode(), response.content)
