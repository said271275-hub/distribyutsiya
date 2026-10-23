from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Prefetch, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_field

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.core.admin_api import audit, company_for_request, transition_order
from apps.core.permissions import CompanyAdminPermission, DriverPermission
from apps.logistics.models import DriverProfile, Trip, TripStop, TripStopOrder, Vehicle
from apps.logistics.routing import (
    calculate_trip_route,
    great_circle_km,
    nearest_neighbor_order,
)
from apps.orders.models import Order, OrderItem


class TripPage(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class TripCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    vehicle_id = serializers.IntegerField(min_value=1)
    driver_id = serializers.IntegerField(min_value=1)


class TripUpdateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    vehicle_id = serializers.IntegerField(min_value=1, required=False)
    driver_id = serializers.IntegerField(min_value=1, required=False)


class TripStopOutputSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    district = serializers.CharField(source="shop.district", read_only=True)
    latitude = serializers.DecimalField(
        source="shop.latitude", max_digits=9, decimal_places=6, read_only=True
    )
    longitude = serializers.DecimalField(
        source="shop.longitude", max_digits=9, decimal_places=6, read_only=True
    )
    order_ids = serializers.SerializerMethodField()

    class Meta:
        model = TripStop
        fields = (
            "id", "shop_id", "shop_name", "district", "latitude", "longitude",
            "sequence", "eta", "eta_window_from", "eta_window_to", "delivered_at",
            "note", "order_ids",
        )

    def get_order_ids(self, stop) -> list[int]:
        links = getattr(stop, "api_order_links", None)
        if links is None:
            links = stop.order_links.all()
        return [link.order_id for link in links]


class TripOutputSerializer(serializers.ModelSerializer):
    vehicle_name = serializers.CharField(source="vehicle.name", read_only=True)
    vehicle_capacity = serializers.DecimalField(
        source="vehicle.capacity", max_digits=12, decimal_places=2, read_only=True
    )
    driver_phone = serializers.CharField(
        source="driver.user.phone", read_only=True
    )
    stops = TripStopOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = (
            "id", "company_id", "date", "vehicle_id", "vehicle_name",
            "vehicle_capacity", "driver_id", "driver_phone", "status",
            "routing_source", "stops", "created_at", "updated_at",
        )


class DriverTripOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit = serializers.CharField(source="product.unit", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("product_name", "unit", "quantity")


class DriverTripOrderSerializer(serializers.ModelSerializer):
    items = DriverTripOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "status", "total_price", "items")


class DriverPickingListItemSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    unit = serializers.CharField()
    quantity = serializers.CharField()


class DriverTripStopSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    address = serializers.CharField(source="shop.address", read_only=True)
    phone = serializers.CharField(source="shop.phone_primary", read_only=True)
    district = serializers.CharField(source="shop.district", read_only=True)
    latitude = serializers.DecimalField(
        source="shop.latitude", max_digits=9, decimal_places=6, read_only=True
    )
    longitude = serializers.DecimalField(
        source="shop.longitude", max_digits=9, decimal_places=6, read_only=True
    )
    orders = serializers.SerializerMethodField()

    class Meta:
        model = TripStop
        fields = (
            "id", "shop_id", "shop_name", "address", "phone", "district", "latitude",
            "longitude", "sequence", "eta", "eta_window_from",
            "eta_window_to", "orders",
        )

    @extend_schema_field(DriverTripOrderSerializer(many=True))
    def get_orders(self, stop) -> list[dict]:
        return DriverTripOrderSerializer(
            [link.order for link in stop.driver_order_links], many=True
        ).data


class DriverTripOutputSerializer(serializers.ModelSerializer):
    vehicle_name = serializers.CharField(source="vehicle.name", read_only=True)
    vehicle_plate_number = serializers.CharField(source="vehicle.plate_number", read_only=True)
    stops = DriverTripStopSerializer(many=True, read_only=True)
    picking_list = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = (
            "id", "date", "vehicle_name", "vehicle_plate_number", "status",
            "stops", "picking_list",
        )

    @extend_schema_field(DriverPickingListItemSerializer(many=True))
    def get_picking_list(self, trip) -> list[dict]:
        totals = {}
        for stop in trip.stops.all():
            for link in stop.driver_order_links:
                for item in link.order.items.all():
                    row = totals.setdefault(item.product_id, {
                        "product_name": item.product.name,
                        "unit": item.product.unit,
                        "quantity": Decimal("0"),
                    })
                    row["quantity"] += item.quantity
        return [
            {**row, "quantity": str(row["quantity"])}
            for row in totals.values()
        ]


class DriverTripQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)


class StopCreateSerializer(serializers.Serializer):
    shop_id = serializers.IntegerField(min_value=1)
    order_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    sequence = serializers.IntegerField(min_value=1, required=False)


class StopOrdersSerializer(serializers.Serializer):
    order_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=True
    )

    def validate_order_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Buyurtma ID sini takrorlamang.")
        return value


class ReorderStopsSerializer(serializers.Serializer):
    stop_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1
    )

    def validate_stop_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("To‘xtash nuqtasi ID sini takrorlamang.")
        return value


class TripConfirmSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
    allow_credit_limit_exceeded = serializers.BooleanField(required=False, default=False)


class TripCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class SuggestTripsSerializer(serializers.Serializer):
    date = serializers.DateField()
    vehicle_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
    )

    def validate_vehicle_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Transport ID sini takrorlamang.")
        return value


class SuggestedStopSerializer(serializers.Serializer):
    shop_id = serializers.IntegerField()
    shop_name = serializers.CharField()
    district = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    order_ids = serializers.ListField(child=serializers.IntegerField())
    estimated_weight = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    estimated_volume = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    capacity_metric = serializers.CharField()
    capacity_load = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )


class SuggestedTripSerializer(serializers.Serializer):
    district = serializers.CharField()
    vehicle_id = serializers.IntegerField(allow_null=True)
    driver_id = serializers.IntegerField(allow_null=True)
    vehicle_capacity = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    capacity_metric = serializers.CharField()
    estimated_load = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    capacity_exceeded = serializers.BooleanField()
    split_for_capacity = serializers.BooleanField()
    warning = serializers.CharField(allow_null=True)
    stops = SuggestedStopSerializer(many=True)
    order_ids = serializers.ListField(child=serializers.IntegerField())


class UnassignedOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    reason = serializers.CharField()


class TripSuggestionResponseSerializer(serializers.Serializer):
    date = serializers.DateField()
    trips = SuggestedTripSerializer(many=True)
    unassigned_order_ids = serializers.ListField(child=serializers.IntegerField())
    unassigned_orders = UnassignedOrderSerializer(many=True)


class TripListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = TripOutputSerializer(many=True)


class TripSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("stop_duration_minutes", "average_route_speed_kph")

    def validate_stop_duration_minutes(self, value):
        if not 1 <= value <= 240:
            raise serializers.ValidationError("To‘xtash vaqti 1–240 daqiqa bo‘lishi kerak.")
        return value

    def validate_average_route_speed_kph(self, value):
        if not 5 <= value <= 120:
            raise serializers.ValidationError("O‘rtacha tezlik 5–120 km/soat bo‘lishi kerak.")
        return value


class DashboardSerializer(serializers.Serializer):
    date = serializers.DateField()
    orders_total = serializers.IntegerField()
    total_volume = serializers.DecimalField(max_digits=20, decimal_places=3)
    delivered = serializers.IntegerField()
    pending = serializers.IntegerField()
    overdue_stops = serializers.IntegerField()
    trips_by_status = serializers.DictField(child=serializers.IntegerField())


def _trip_queryset(company, *, driver=None, driver_details=False):
    queryset = Trip.objects.filter(company=company).select_related(
        "company", "vehicle", "driver__user"
    ).prefetch_related("stops__shop")
    if driver_details:
        queryset = queryset.prefetch_related(Prefetch(
            "stops__order_links",
            queryset=TripStopOrder.objects.select_related("order").prefetch_related(
                "order__items__product"
            ),
            to_attr="driver_order_links",
        ))
    else:
        queryset = queryset.prefetch_related("stops__order_links")
    if driver is not None:
        queryset = queryset.filter(driver__user=driver)
    return queryset.order_by("-date", "-created_at")


def _move_stop_order_links(*, trip, stop, order_ids):
    if trip.status != Trip.Status.PLANNED:
        raise ValidationError({"trip": "Faqat rejalashtirilgan reysni o‘zgartirish mumkin."})
    orders = list(
        Order.objects.filter(
            pk__in=order_ids,
            company=trip.company,
            shop=stop.shop,
            delivery_date=trip.date,
            status__in=(Order.Status.NEW, Order.Status.CONFIRMED),
        ).order_by("pk")
    )
    if len(orders) != len(order_ids):
        raise ValidationError(
            {"order_ids": "Buyurtmalar reys, sana, do‘kon va holatga mos bo‘lishi kerak."}
        )
    occupied = TripStopOrder.objects.filter(order_id__in=order_ids).exclude(
        trip_stop=stop
    )
    if occupied.exists():
        raise ValidationError({"order_ids": "Buyurtmalardan biri boshqa reysga biriktirilgan."})

    TripStopOrder.objects.filter(trip_stop=stop).exclude(
        order_id__in=order_ids
    ).delete()
    existing_ids = set(
        TripStopOrder.objects.filter(trip_stop=stop).values_list("order_id", flat=True)
    )
    for order in orders:
        if order.pk not in existing_ids:
            link = TripStopOrder(
                company=trip.company, trip_stop=stop, order=order
            )
            link.full_clean()
            link.save()
    return orders


def _resequence_stops(trip, stops):
    for offset, stop in enumerate(stops, start=1):
        TripStop.objects.filter(pk=stop.pk).update(sequence=1000000 + offset)
    for sequence, stop in enumerate(stops, start=1):
        stop.sequence = sequence
        stop.save(update_fields=("sequence", "updated_at"))


def _shop_load(orders):
    weight = Decimal("0")
    volume = Decimal("0")
    known_weight = True
    known_volume = True
    order_ids = []
    for order in orders:
        order_ids.append(order.pk)
        for item in order.items.all():
            if item.product.unit_weight is None:
                known_weight = False
            else:
                weight += item.quantity * item.product.unit_weight
            if item.product.unit_volume is None:
                known_volume = False
            else:
                volume += item.quantity * item.product.unit_volume
    if known_weight:
        metric, load = "weight", weight
    elif known_volume:
        metric, load = "volume", volume
    else:
        metric, load = "unknown", None
    return {
        "order_ids": order_ids,
        "estimated_weight": weight if known_weight else None,
        "estimated_volume": volume if known_volume else None,
        "capacity_metric": metric,
        "capacity_load": load,
    }


def _vehicle_capacity(vehicle, metric):
    if metric == "weight":
        return vehicle.capacity
    if metric == "volume":
        return vehicle.volume_capacity
    return None


def _cluster_shops(shops):
    remaining = list(shops)
    clusters = []
    radius = settings.TRIP_CLUSTER_RADIUS_KM
    while remaining:
        if len(remaining) == 1:
            clusters.append([remaining.pop()])
            continue
        seed = min(
            remaining,
            key=lambda shop: (
                sum(
                    great_circle_km(
                        (float(shop.latitude), float(shop.longitude)),
                        (float(other.latitude), float(other.longitude)),
                    )
                    for other in remaining if other.pk != shop.pk
                ),
                shop.pk,
            ),
        )
        cluster = [seed]
        remaining.remove(seed)
        while remaining:
            center = (
                sum(float(shop.latitude) for shop in cluster) / len(cluster),
                sum(float(shop.longitude) for shop in cluster) / len(cluster),
            )
            candidate = min(
                remaining,
                key=lambda shop: (
                    great_circle_km(
                        center, (float(shop.latitude), float(shop.longitude))
                    ),
                    shop.pk,
                ),
            )
            if great_circle_km(
                center, (float(candidate.latitude), float(candidate.longitude))
            ) > radius:
                break
            cluster.append(candidate)
            remaining.remove(candidate)
        clusters.append(cluster)
    return clusters


def _nearest_shop_order(shops):
    if len(shops) < 2:
        return shops
    coordinates = [
        (float(shop.latitude), float(shop.longitude)) for shop in shops
    ]
    distances = [
        [great_circle_km(first, second) for second in coordinates]
        for first in coordinates
    ]
    return [shops[index] for index in nearest_neighbor_order(distances)]


def build_trip_suggestions(*, company, delivery_date, vehicle_ids=None):
    orders = list(
        Order.objects.filter(
            company=company,
            delivery_date=delivery_date,
            status=Order.Status.CONFIRMED,
            shop__company_links__company=company,
            shop__company_links__is_active=True,
        )
        .exclude(trip_stop_links__isnull=False)
        .select_related("shop")
        .prefetch_related("items__product")
        .distinct()
        .order_by("shop__district", "shop_id", "pk")
    )
    if not orders:
        return {
            "date": delivery_date,
            "trips": [],
            "unassigned_order_ids": [],
            "unassigned_orders": [],
        }

    orders_by_shop = defaultdict(list)
    for order in orders:
        orders_by_shop[order.shop_id].append(order)
    shops = {
        shop_id: rows[0].shop for shop_id, rows in orders_by_shop.items()
    }
    loads = {
        shop_id: _shop_load(rows) for shop_id, rows in orders_by_shop.items()
    }
    weight_is_complete = all(
        load["estimated_weight"] is not None for load in loads.values()
    )
    volume_is_complete = all(
        load["estimated_volume"] is not None for load in loads.values()
    )
    capacity_metric = (
        "weight" if weight_is_complete
        else "volume" if volume_is_complete
        else "unknown"
    )
    for load in loads.values():
        load["capacity_metric"] = capacity_metric
        load["capacity_load"] = load[f"estimated_{capacity_metric}"] if (
            capacity_metric != "unknown"
        ) else None

    by_district = defaultdict(list)
    for shop in shops.values():
        by_district[shop.district.strip().casefold()].append(shop)

    vehicles_query = Vehicle.objects.filter(
        company=company, is_active=True, is_archived=False
    )
    if vehicle_ids:
        valid_vehicle_ids = set(vehicles_query.filter(pk__in=vehicle_ids).values_list(
            "pk", flat=True
        ))
        if valid_vehicle_ids != set(vehicle_ids):
            raise ValidationError({"vehicle_ids": "Transportlardan biri kompaniyaga tegishli emas yoki faol emas."})
        vehicles_query = vehicles_query.filter(pk__in=vehicle_ids)
    occupied_trips = Trip.objects.filter(
    company=company,
    date=delivery_date,
    ).exclude(status=Trip.Status.CANCELLED)
    capacity_field = "volume_capacity" if capacity_metric == "volume" else "capacity"
    vehicles = list(
        vehicles_query.exclude(
            pk__in=occupied_trips.values("vehicle_id")
        ).order_by(F(capacity_field).desc(nulls_last=True), "pk")
    )
    drivers = list(
        DriverProfile.objects.filter(
            company=company,
            user__is_active=True,
            user__is_blocked=False,
        )
        .exclude(pk__in=occupied_trips.values("driver_id"))
        .select_related("vehicle")
        .order_by("pk")
    )
    assigned_drivers = defaultdict(list)
    unassigned_drivers = []
    for driver in drivers:
        if driver.vehicle_id:
            assigned_drivers[driver.vehicle_id].append(driver)
        else:
            unassigned_drivers.append(driver)
    vehicle_driver_pairs = []
    for vehicle in vehicles:
        available_drivers = assigned_drivers.get(vehicle.pk, [])
        if available_drivers:
            vehicle_driver_pairs.append((vehicle, available_drivers.pop(0)))
        elif unassigned_drivers:
            vehicle_driver_pairs.append((vehicle, unassigned_drivers.pop(0)))
    next_pair_index = 0
    unassigned_order_ids = set()

    suggestions = []
    for district_key in sorted(by_district):
        district_shops = by_district[district_key]
        for cluster in _cluster_shops(district_shops):
            ordered = _nearest_shop_order(cluster)
            current = []
            current_load = Decimal("0")
            current_metric = None
            current_vehicle = None
            current_driver = None

            def flush(*, split_for_capacity=False):
                nonlocal current, current_load, current_metric
                nonlocal current_vehicle, current_driver
                if not current:
                    return
                all_order_ids = [
                    order_id
                    for stop in current
                    for order_id in stop["order_ids"]
                ]
                over_capacity = bool(
                    current_vehicle is not None
                    and current_metric in ("weight", "volume")
                    and _vehicle_capacity(current_vehicle, current_metric) is not None
                    and current_load > _vehicle_capacity(current_vehicle, current_metric)
                )
                capacity_missing = (
                    current_vehicle is not None
                    and current_metric in ("weight", "volume")
                    and _vehicle_capacity(current_vehicle, current_metric) is None
                )
                suggestions.append({
                    "district": current[0]["district"],
                    "vehicle_id": current_vehicle.pk,
                    "driver_id": current_driver.pk,
                    "vehicle_capacity": _vehicle_capacity(current_vehicle, current_metric),
                    "capacity_metric": current_metric or "unknown",
                    "estimated_load": current_load if current_metric else None,
                    "capacity_exceeded": over_capacity,
                    "split_for_capacity": split_for_capacity,
                    "warning": (
                        "Bitta do‘kon buyurtmasi transport sig‘imidan oshadi."
                        if over_capacity
                        else "Transport uchun bu o‘lchovdagi sig‘im kiritilmagan; sig‘imni tekshiring."
                        if capacity_missing
                        else "Sig‘im chegarasi sabab keyingi nuqtalar alohida reysga taklif qilindi."
                        if split_for_capacity
                        else None
                    ),
                    "stops": current,
                    "order_ids": all_order_ids,
                })
                current = []
                current_load = Decimal("0")
                current_metric = None
                current_vehicle = None
                current_driver = None

            for shop in ordered:
                load = loads[shop.pk]
                metric = load["capacity_metric"]
                next_load = load["capacity_load"]
                if not current:
                    if next_pair_index >= len(vehicle_driver_pairs):
                        unassigned_order_ids.update(load["order_ids"])
                        continue
                    current_vehicle, current_driver = vehicle_driver_pairs[
                        next_pair_index
                    ]
                    next_pair_index += 1
                if (
                    current
                    and current_vehicle is not None
                    and metric == current_metric
                    and next_load is not None
                    and _vehicle_capacity(current_vehicle, metric) is not None
                    and current_load + next_load > _vehicle_capacity(current_vehicle, metric)
                ):
                    flush(split_for_capacity=True)
                    if next_pair_index >= len(vehicle_driver_pairs):
                        unassigned_order_ids.update(load["order_ids"])
                        continue
                    current_vehicle, current_driver = vehicle_driver_pairs[
                        next_pair_index
                    ]
                    next_pair_index += 1
                current_metric = metric if current_metric is None else current_metric
                current_load += next_load or Decimal("0")
                current.append({
                    "shop_id": shop.pk,
                    "shop_name": shop.name,
                    "district": shop.district,
                    "latitude": shop.latitude,
                    "longitude": shop.longitude,
                    **load,
                })
            flush()

    assigned = {
        order_id for suggestion in suggestions for order_id in suggestion["order_ids"]
    }
    unassigned_order_ids.update(
        order.pk for order in orders if order.pk not in assigned
    )
    unassigned_reason = (
        "Taqsimlanmagan (mashina yetmadi): shu sana uchun boshqa faol "
        "mashina yoki haydovchi qolmadi."
    )
    return {
        "date": delivery_date,
        "trips": suggestions,
        "unassigned_order_ids": [
            order.pk for order in orders if order.pk in unassigned_order_ids
        ],
        "unassigned_orders": [
            {"order_id": order.pk, "reason": unassigned_reason}
            for order in orders if order.pk in unassigned_order_ids
        ],
    }


class TripAdminViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    pagination_class = TripPage
    serializer_class = TripOutputSerializer
    lookup_value_regex = r"\d+"

    @property
    def company(self):
        return company_for_request(self.request)

    def get_queryset(self):
        return _trip_queryset(self.company)

    @extend_schema(responses=TripListResponseSerializer)
    def list(self, request):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.get_queryset(), request, view=self)
        return paginator.get_paginated_response(TripOutputSerializer(page, many=True).data)

    @extend_schema(request=TripCreateSerializer, responses={201: TripOutputSerializer})
    def create(self, request):
        serializer = TripCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        company = self.company
        vehicle = get_object_or_404(
            Vehicle.objects.filter(
                company=company, is_active=True, is_archived=False
            ),
            pk=values["vehicle_id"],
        )
        driver = get_object_or_404(
            DriverProfile.objects.filter(
                company=company,
                user__is_active=True,
                user__is_blocked=False,
            ),
            pk=values["driver_id"],
        )
        trip = Trip(company=company, vehicle=vehicle, driver=driver, date=values["date"])
        trip.full_clean()
        trip.save()
        audit(request.user, company, "create", trip, after={
            "date": trip.date, "vehicle_id": vehicle.pk, "driver_id": driver.pk,
        })
        return Response(
            TripOutputSerializer(self.get_queryset().get(pk=trip.pk)).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses=TripOutputSerializer)
    def retrieve(self, request, pk=None):
        trip = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(TripOutputSerializer(trip).data)

    @extend_schema(request=TripUpdateSerializer, responses=TripOutputSerializer)
    def partial_update(self, request, pk=None):
        trip = get_object_or_404(self.get_queryset(), pk=pk)
        if trip.status != Trip.Status.PLANNED:
            raise ValidationError({"trip": "Faqat rejalashtirilgan reysni tahrirlash mumkin."})
        serializer = TripUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        before = {"date": trip.date, "vehicle_id": trip.vehicle_id, "driver_id": trip.driver_id}
        if "vehicle_id" in values:
            trip.vehicle = get_object_or_404(
                Vehicle.objects.filter(company=self.company, is_active=True, is_archived=False),
                pk=values["vehicle_id"],
            )
        if "driver_id" in values:
            trip.driver = get_object_or_404(
                DriverProfile.objects.filter(
                    company=self.company, user__is_active=True, user__is_blocked=False
                ),
                pk=values["driver_id"],
            )
        if "date" in values:
            if trip.stops.exists():
                raise ValidationError({"date": "To‘xtash nuqtalari bor reys sanasini o‘zgartirib bo‘lmaydi."})
            trip.date = values["date"]
        trip.full_clean()
        trip.save()
        audit(request.user, self.company, "update", trip, before, {
            "date": trip.date, "vehicle_id": trip.vehicle_id, "driver_id": trip.driver_id,
        })
        return Response(TripOutputSerializer(self.get_queryset().get(pk=trip.pk)).data)

    def _get_trip(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    @extend_schema(request=StopCreateSerializer, responses={201: TripStopOutputSerializer})
    @action(detail=True, methods=("post",), url_path="stops")
    @transaction.atomic
    def add_stop(self, request, pk=None):
        trip = self._get_trip(pk)
        if trip.status != Trip.Status.PLANNED:
            raise ValidationError({"trip": "Faqat rejalashtirilgan reysni o‘zgartirish mumkin."})
        serializer = StopCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        shop = get_object_or_404(
            Shop.objects.filter(
                company_links__company=self.company,
                company_links__is_active=True,
            ).distinct(),
            pk=values["shop_id"],
        )
        stop = trip.stops.filter(shop=shop).first()
        if stop is None:
            sequence = trip.stops.count() + 1
            stop = TripStop(
                company=self.company,
                trip=trip,
                shop=shop,
                sequence=sequence,
                note=values.get("note", ""),
            )
            stop.full_clean()
            stop.save()
            stops = list(trip.stops.exclude(pk=stop.pk).order_by("sequence", "pk"))
            requested_sequence = min(values.get("sequence", sequence), len(stops) + 1)
            stops.insert(requested_sequence - 1, stop)
            _resequence_stops(trip, stops)
        if values["order_ids"]:
            current_ids = list(
                TripStopOrder.objects.filter(trip_stop=stop).values_list("order_id", flat=True)
            )
            _move_stop_order_links(
                trip=trip, stop=stop,
                order_ids=list(dict.fromkeys(current_ids + values["order_ids"])),
            )
        audit(request.user, self.company, "trip.stop.add", stop, after={
            "trip_id": trip.pk, "shop_id": shop.pk,
            "order_ids": list(stop.order_links.values_list("order_id", flat=True)),
        })
        stop = trip.stops.select_related("shop").prefetch_related("order_links").get(pk=stop.pk)
        return Response(TripStopOutputSerializer(stop).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReorderStopsSerializer, responses=TripOutputSerializer)
    @action(detail=True, methods=("post",), url_path="stops/reorder")
    @transaction.atomic
    def reorder_stops(self, request, pk=None):
        trip = self._get_trip(pk)
        if trip.status != Trip.Status.PLANNED:
            raise ValidationError({"trip": "Faqat rejalashtirilgan reysni o‘zgartirish mumkin."})
        serializer = ReorderStopsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stops = list(trip.stops.order_by("sequence", "pk"))
        ids = serializer.validated_data["stop_ids"]
        if set(ids) != {stop.pk for stop in stops}:
            raise ValidationError({"stop_ids": "Barcha reys nuqtalarini aynan bir marta yuboring."})
        _resequence_stops(trip, [next(stop for stop in stops if stop.pk == pk) for pk in ids])
        audit(request.user, self.company, "trip.stops.reorder", trip, after={"stop_ids": ids})
        return Response(TripOutputSerializer(self.get_queryset().get(pk=trip.pk)).data)

    @extend_schema(request=None, responses=TripOutputSerializer)
    @action(
        detail=True, methods=("delete",),
        url_path=r"stops/(?P<stop_id>\d+)",
    )
    @transaction.atomic
    def remove_stop(self, request, pk=None, stop_id=None):
        trip = self._get_trip(pk)
        if trip.status != Trip.Status.PLANNED:
            raise ValidationError({"trip": "Faqat rejalashtirilgan reysni o‘zgartirish mumkin."})
        stop = get_object_or_404(trip.stops, pk=stop_id)
        before = {
            "shop_id": stop.shop_id,
            "order_ids": list(stop.order_links.values_list("order_id", flat=True)),
        }
        stop.delete()
        _resequence_stops(trip, list(trip.stops.order_by("sequence", "pk")))
        audit(request.user, self.company, "trip.stop.remove", trip, before, None)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=TripConfirmSerializer, responses=TripOutputSerializer)
    @action(detail=True, methods=("post",), url_path="confirm")
    @transaction.atomic
    def confirm(self, request, pk=None):
        trip = self._get_trip(pk)
        if trip.status != Trip.Status.PLANNED:
            raise ValidationError({"trip": "Faqat rejalashtirilgan reysni tasdiqlash mumkin."})
        if not trip.stops.exists():
            raise ValidationError({"trip": "Tasdiqlashdan oldin reysga nuqta qo‘shing."})
        serializer = TripConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        links = list(
            TripStopOrder.objects.filter(trip_stop__trip=trip)
            .select_related("order").order_by("trip_stop__sequence", "order_id")
        )
        order_ids = [link.order_id for link in links]
        if len(order_ids) != len(set(order_ids)):
            raise ValidationError({"trip": "Buyurtma reysda takrorlangan."})
        for link in links:
            order = link.order
            if order.company_id != trip.company_id or order.shop_id != link.trip_stop.shop_id:
                raise ValidationError({"trip": "Reysdagi buyurtma kompaniya yoki do‘koniga mos emas."})
            if order.delivery_date != trip.date:
                raise ValidationError({"trip": "Buyurtma va reys sanasi mos bo‘lishi kerak."})
            if order.status == Order.Status.NEW:
                transition_order(
                    order=order,
                    actor=request.user,
                    target=Order.Status.CONFIRMED,
                    reason=serializer.validated_data["reason"],
                    allow_credit_limit_exceeded=serializer.validated_data[
                        "allow_credit_limit_exceeded"
                    ],
                )
            elif order.status != Order.Status.CONFIRMED:
                raise ValidationError({"trip": "Faqat yangi yoki tasdiqlangan buyurtmalarni reysga tasdiqlash mumkin."})
        source = calculate_trip_route(trip)
        trip.status = Trip.Status.CONFIRMED
        trip.save(update_fields=("status", "updated_at"))
        audit(request.user, self.company, "trip.confirm", trip, {
            "status": Trip.Status.PLANNED,
        }, {
            "status": trip.status, "order_ids": order_ids, "routing_source": source,
        })
        return Response(TripOutputSerializer(self.get_queryset().get(pk=trip.pk)).data)

    @extend_schema(request=TripCancelSerializer, responses=TripOutputSerializer)
    @action(detail=True, methods=("post",), url_path="cancel")
    @transaction.atomic
    def cancel(self, request, pk=None):
        trip = self._get_trip(pk)
        if trip.status not in (Trip.Status.PLANNED, Trip.Status.CONFIRMED):
            raise ValidationError({"trip": "Faqat rejalashtirilgan yoki tasdiqlangan reys bekor qilinadi."})
        serializer = TripCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        before = {
            "status": trip.status,
            "order_ids": list(
                TripStopOrder.objects.filter(trip_stop__trip=trip).values_list("order_id", flat=True)
            ),
        }
        trip.status = Trip.Status.CANCELLED
        trip.save(update_fields=("status", "updated_at"))
        trip.stops.all().delete()
        audit(request.user, self.company, "trip.cancel", trip, before, {
            "status": trip.status, "reason": serializer.validated_data["reason"],
        })
        return Response(TripOutputSerializer(self.get_queryset().get(pk=trip.pk)).data)

    @extend_schema(request=None, responses=TripOutputSerializer)
    @action(detail=True, methods=("post",), url_path="route")
    @transaction.atomic
    def calculate_route(self, request, pk=None):
        trip = self._get_trip(pk)
        if trip.status not in (Trip.Status.PLANNED, Trip.Status.CONFIRMED):
            raise ValidationError({"trip": "Bu reys marshrutini qayta hisoblab bo‘lmaydi."})
        source = calculate_trip_route(trip)
        audit(request.user, self.company, "trip.route.calculate", trip, after={
            "routing_source": source,
            "stop_ids": list(trip.stops.order_by("sequence").values_list("id", flat=True)),
        })
        return Response(TripOutputSerializer(self.get_queryset().get(pk=trip.pk)).data)

    @extend_schema(
        request=SuggestTripsSerializer,
        responses=TripSuggestionResponseSerializer,
    )
    @action(detail=False, methods=("post",), url_path="suggest")
    def suggest(self, request):
        serializer = SuggestTripsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        result = build_trip_suggestions(
            company=self.company,
            delivery_date=values["date"],
            vehicle_ids=values.get("vehicle_ids"),
        )
        return Response(result)


class TripStopOrdersView(APIView):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)

    @extend_schema(request=StopOrdersSerializer, responses=TripOutputSerializer)
    @transaction.atomic
    def put(self, request, trip_id, stop_id):
        company = company_for_request(request)
        trip = get_object_or_404(Trip.objects.filter(company=company), pk=trip_id)
        stop = get_object_or_404(TripStop.objects.filter(trip=trip), pk=stop_id)
        serializer = StopOrdersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        before = list(stop.order_links.values_list("order_id", flat=True))
        orders = _move_stop_order_links(
            trip=trip, stop=stop, order_ids=serializer.validated_data["order_ids"]
        )
        audit(request.user, company, "trip.stop.orders.replace", stop, {
            "order_ids": before,
        }, {"order_ids": [order.pk for order in orders]})
        result = _trip_queryset(company).get(pk=trip.pk)
        return Response(TripOutputSerializer(result).data)


class DriverTripListView(APIView):
    permission_classes = (IsAuthenticated, DriverPermission)

    @extend_schema(parameters=[DriverTripQuerySerializer], responses=DriverTripOutputSerializer(many=True))
    def get(self, request):
        query = DriverTripQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        trip_date = query.validated_data.get("date", timezone.localdate())
        trips = _trip_queryset(
            request.user.company, driver=request.user, driver_details=True
        ).filter(
            date=trip_date
        ).exclude(status=Trip.Status.CANCELLED)
        return Response(DriverTripOutputSerializer(trips, many=True).data)


class RouteSettingsView(APIView):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)

    @extend_schema(responses=TripSettingsSerializer)
    def get(self, request):
        return Response(TripSettingsSerializer(company_for_request(request)).data)

    @extend_schema(request=TripSettingsSerializer, responses=TripSettingsSerializer)
    def patch(self, request):
        company = company_for_request(request)
        serializer = TripSettingsSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = {
            "stop_duration_minutes": company.stop_duration_minutes,
            "average_route_speed_kph": company.average_route_speed_kph,
        }
        serializer.save()
        AuditLog.objects.create(
            actor=request.user,
            company=company,
            action="route.settings.update",
            entity_type="Company",
            entity_id=str(company.pk),
            before=before,
            after=serializer.data,
        )
        return Response(serializer.data)


class DashboardView(APIView):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)

    @extend_schema(responses=DashboardSerializer)
    def get(self, request):
        company = company_for_request(request)
        today = timezone.localdate()
        orders = Order.objects.filter(company=company, delivery_date=today)
        volume_rows = (
            orders.values("items__product__unit_volume")
            .annotate(quantity=Sum("items__quantity"))
        )
        total_volume = sum(
            (
                row["items__product__unit_volume"] * row["quantity"]
                for row in volume_rows
                if row["items__product__unit_volume"] is not None
            ),
            Decimal("0"),
        )
        delivered = orders.filter(status=Order.Status.DELIVERED).count()
        pending = orders.exclude(
            status__in=(Order.Status.DELIVERED, Order.Status.CANCELLED)
        ).count()
        now = timezone.now()
        overdue = TripStop.objects.filter(
            company=company,
            delivered_at__isnull=True,
            eta_window_to__lt=now,
            trip__status__in=(Trip.Status.CONFIRMED, Trip.Status.IN_PROGRESS),
        ).count()
        trips_by_status = {
            row["status"]: row["count"]
            for row in Trip.objects.filter(company=company, date=today)
            .values("status").annotate(count=Count("id"))
        }
        return Response(DashboardSerializer({
            "date": today,
            "orders_total": orders.count(),
            "total_volume": total_volume,
            "delivered": delivered,
            "pending": pending,
            "overdue_stops": overdue,
            "trips_by_status": trips_by_status,
        }).data)
