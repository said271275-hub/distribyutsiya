from decimal import Decimal

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_field

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.catalog.shop_api import ShopCatalogProductSerializer
from apps.companies.models import CompanyShopLink, Shop, ShopPrice
from apps.core.permissions import ShopOwnerPermission
from apps.logistics.models import Trip, TripStopOrder
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.orders.shop_services import cancel_shop_order, create_shop_order, update_shop_order


class ShopOrderPagination(PageNumberPagination):
    page_size = 20


class OrderLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class ShopOrderWriteSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(min_value=1, required=False)
    delivery_date = serializers.DateField(required=False)
    delivery_time_from = serializers.TimeField(required=False, allow_null=True)
    delivery_time_to = serializers.TimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    items = OrderLineInputSerializer(many=True, min_length=1, required=False)

    def validate(self, attrs):
        if not self.partial:
            required = ("company_id", "delivery_date", "items")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError({field: "Bu maydon majburiy." for field in missing})
        if "items" in attrs:
            product_ids = [item["product_id"] for item in attrs["items"]]
            if len(product_ids) != len(set(product_ids)):
                raise serializers.ValidationError({"items": "Bir mahsulotni takrorlamang."})
        return attrs


class ShopOrderCancelSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ShopOrderRepeatSerializer(serializers.Serializer):
    delivery_date = serializers.DateField()
    delivery_time_from = serializers.TimeField(required=False, allow_null=True)
    delivery_time_to = serializers.TimeField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=5000)


class ShopOrderRepeatCartLineSerializer(serializers.Serializer):
    product = ShopCatalogProductSerializer(read_only=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)


class ShopOrderRepeatCartSerializer(serializers.Serializer):
    items = ShopOrderRepeatCartLineSerializer(many=True)
    omitted_count = serializers.IntegerField()


class OrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit = serializers.CharField(source="product.unit", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product_id", "product_name", "unit", "quantity", "unit_price", "line_total")


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    actor_phone = serializers.CharField(source="actor.phone", read_only=True, allow_null=True)

    class Meta:
        model = OrderStatusHistory
        fields = ("from_status", "status", "actor_phone", "note", "created_at")


class ShopOrderSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    items = OrderLineSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    eta = serializers.SerializerMethodField()
    eta_window_from = serializers.SerializerMethodField()
    eta_window_to = serializers.SerializerMethodField()
    driver_phone = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id", "company_id", "company_name", "shop_id", "shop_name", "status", "delivery_date",
            "delivery_time_from", "delivery_time_to", "total_price", "note", "items",
            "status_history", "eta", "eta_window_from", "eta_window_to",
            "driver_phone", "created_at", "updated_at",
        )

    def _trip_stop(self, order):
        links = getattr(order, "shop_trip_links", None)
        if links is None:
            links = order.trip_stop_links.filter(
                trip_stop__trip__status__in=(
                    Trip.Status.CONFIRMED,
                    Trip.Status.IN_PROGRESS,
                )
            ).select_related(
                "trip_stop__trip__driver__user"
            ).order_by("trip_stop__sequence")
        return links[0].trip_stop if links else None

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_eta(self, order):
        stop = self._trip_stop(order)
        return stop.eta if stop else None

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_eta_window_from(self, order):
        stop = self._trip_stop(order)
        return stop.eta_window_from if stop else None

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_eta_window_to(self, order):
        stop = self._trip_stop(order)
        return stop.eta_window_to if stop else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_driver_phone(self, order):
        stop = self._trip_stop(order)
        return stop.trip.driver.user.phone if stop else None


class ShopOrderBaseView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)
    serializer_class = ShopOrderSerializer

    def get_shop(self, user):
        return get_object_or_404(Shop, owner=user)

    def get_order(self, user, pk):
        return get_object_or_404(
            Order.objects.filter(shop__owner=user)
            .select_related("company")
            .prefetch_related(
                "items__product",
                "status_history__actor",
                Prefetch(
                    "trip_stop_links",
                    queryset=TripStopOrder.objects.filter(
                        trip_stop__trip__status__in=(
                            Trip.Status.CONFIRMED,
                            Trip.Status.IN_PROGRESS,
                        )
                    ).select_related(
                        "trip_stop__trip__driver__user"
                    ),
                    to_attr="shop_trip_links",
                ),
            ),
            pk=pk,
        )


class ShopOrderListCreateView(ShopOrderBaseView):
    @extend_schema(responses=ShopOrderSerializer(many=True))
    def get(self, request):
        shop = self.get_shop(request.user)
        orders = (
            Order.objects.filter(shop=shop)
            .select_related("company")
            .prefetch_related(
                "items__product",
                "status_history__actor",
                Prefetch(
                    "trip_stop_links",
                    queryset=TripStopOrder.objects.filter(
                        trip_stop__trip__status__in=(
                            Trip.Status.CONFIRMED,
                            Trip.Status.IN_PROGRESS,
                        )
                    ).select_related("trip_stop__trip__driver__user"),
                    to_attr="shop_trip_links",
                ),
            )
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            if status_filter not in Order.Status.values:
                raise ValidationError({"status": "Buyurtma holati noto‘g‘ri."})
            orders = orders.filter(status=status_filter)
        paginator = ShopOrderPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        return paginator.get_paginated_response(ShopOrderSerializer(page, many=True).data)

    @extend_schema(request=ShopOrderWriteSerializer, responses={201: ShopOrderSerializer})
    def post(self, request):
        serializer = ShopOrderWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = create_shop_order(user=request.user, data=serializer.validated_data)
        return Response(ShopOrderSerializer(order).data, status=201)


class ShopOrderDetailView(ShopOrderBaseView):
    @extend_schema(responses=ShopOrderSerializer)
    def get(self, request, pk):
        order = self.get_order(request.user, pk)
        return Response(ShopOrderSerializer(order).data)

    @extend_schema(request=ShopOrderWriteSerializer, responses=ShopOrderSerializer)
    def patch(self, request, pk):
        order = self.get_order(request.user, pk)
        serializer = ShopOrderWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        order = update_shop_order(order=order, user=request.user, data=serializer.validated_data)
        return Response(ShopOrderSerializer(self.get_order(request.user, pk)).data)


class ShopOrderCancelView(ShopOrderBaseView):
    @extend_schema(request=ShopOrderCancelSerializer, responses=ShopOrderSerializer)
    def post(self, request, pk):
        order = self.get_order(request.user, pk)
        serializer = ShopOrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = cancel_shop_order(
            order=order, user=request.user, note=serializer.validated_data.get("note", "")
        )
        return Response(ShopOrderSerializer(self.get_order(request.user, pk)).data)


class ShopOrderRepeatView(ShopOrderBaseView):
    @extend_schema(request=ShopOrderRepeatSerializer, responses={201: ShopOrderSerializer})
    def post(self, request, pk):
        previous = self.get_order(request.user, pk)
        serializer = ShopOrderRepeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repeat_data = serializer.validated_data
        data = {
            "company_id": previous.company_id,
            "delivery_date": repeat_data["delivery_date"],
            "delivery_time_from": repeat_data.get("delivery_time_from"),
            "delivery_time_to": repeat_data.get("delivery_time_to"),
            "note": repeat_data.get("note", previous.note),
            "items": [
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in previous.items.all()
            ],
        }
        serializer = ShopOrderWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        order = create_shop_order(user=request.user, data=serializer.validated_data, source_order=previous)
        return Response(ShopOrderSerializer(order).data, status=201)


class ShopOrderRepeatCartView(ShopOrderBaseView):
    @extend_schema(responses=ShopOrderRepeatCartSerializer)
    def get(self, request):
        shop = self.get_shop(request.user)
        latest_order = (
            Order.objects.filter(shop=shop).order_by("-created_at", "-pk").first()
        )
        if latest_order is None:
            return Response({"items": [], "omitted_count": 0})

        previous_items = list(latest_order.items.select_related("product").all())
        linked_company = CompanyShopLink.objects.filter(
            shop=shop,
            company_id=latest_order.company_id,
            is_active=True,
            company__is_active=True,
        ).exists()
        products = Product.objects.none()
        if linked_company:
            products = (
                Product.objects.filter(
                    pk__in=[item.product_id for item in previous_items],
                    company_id=latest_order.company_id,
                    is_active=True,
                    is_archived=False,
                )
                .select_related("company")
                .prefetch_related(
                    Prefetch(
                        "shop_prices",
                        queryset=ShopPrice.objects.filter(shop=shop),
                        to_attr="shop_specific_prices",
                    )
                )
            )

        product_data = {
            product["id"]: product
            for product in ShopCatalogProductSerializer(
                products, many=True, context={"request": request}
            ).data
        }
        cart_items = [
            {"product": product_data[item.product_id], "quantity": item.quantity}
            for item in previous_items
            if item.product_id in product_data
        ]
        return Response({
            "items": cart_items,
            "omitted_count": len(previous_items) - len(cart_items),
        })