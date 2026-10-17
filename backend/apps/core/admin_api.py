import json
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_field

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.core.permissions import CompanyAdminPermission
from apps.logistics.models import DriverProfile, Trip, Vehicle
from apps.orders.models import Order, OrderStatusHistory
from apps.orders.shop_api import ShopOrderSerializer
from apps.payments.models import BalanceEntry, Payment, ShopBalance


def company_for_request(request):
    user = request.user
    if user.role == User.Role.SUPER_ADMIN:
        company_id = request.query_params.get("company_id") or request.data.get("company_id")
        if not company_id:
            raise ValidationError({"company_id": "Super admin kompaniya ID sini yuborishi kerak."})
        try:
            return get_object_or_404(Company, pk=int(company_id))
        except (TypeError, ValueError) as error:
            raise ValidationError({"company_id": "Kompaniya ID raqami noto‘g‘ri."}) from error
    if not user.company_id:
        raise PermissionDenied("Foydalanuvchi kompaniyaga biriktirilmagan.")
    return user.company


def audit(actor, company, action_name, entity, before=None, after=None):
    AuditLog.objects.create(
        company=company,
        actor=actor,
        action=action_name,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        before=json.loads(json.dumps(before, default=str)) if before is not None else None,
        after=json.loads(json.dumps(after, default=str)) if after is not None else None,
    )


def snapshot(instance):
    return model_to_dict(instance)


def order_state(order):
    return {
        "status": order.status,
        "total_price": str(order.total_price),
        "shop_id": order.shop_id,
    }


class CreditLimitExceeded(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "credit_limit_exceeded"

    def __init__(self, balance, limit, order_total):
        super().__init__({
            "warning": "Buyurtma do‘konning qarz limitidan oshadi.",
            "current_balance": str(balance),
            "credit_limit": str(limit),
            "order_total": str(order_total),
            "allow_credit_limit_exceeded": "Tasdiqlash uchun true yuboring.",
        })


ORDER_TRANSITIONS = {
    Order.Status.NEW: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.LOADED, Order.Status.CANCELLED},
    Order.Status.LOADED: {Order.Status.IN_TRANSIT},
    Order.Status.IN_TRANSIT: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_order(*, order, actor, target, reason, allow_credit_limit_exceeded=False):
    order = Order.objects.select_for_update().select_related("shop", "company").get(pk=order.pk)
    previous = order.status
    if target not in ORDER_TRANSITIONS.get(previous, set()):
        raise ValidationError({"status": f"{previous} holatidan {target} holatiga o‘tib bo‘lmaydi."})
    if not reason.strip():
        raise ValidationError({"reason": "Holat o‘zgarishi sababini kiriting."})

    if target == Order.Status.CONFIRMED:
        if order.total_price <= 0:
            raise ValidationError({"order": "Nol qiymatli buyurtmani tasdiqlab bo‘lmaydi."})
        balance, _ = ShopBalance.objects.get_or_create(
            company=order.company, shop=order.shop
        )
        balance = ShopBalance.objects.select_for_update().get(pk=balance.pk)
        limit = balance.credit_limit
        projected = balance.current_balance + order.total_price
        if (
            limit is not None
            and projected > limit
            and not allow_credit_limit_exceeded
        ):
            raise CreditLimitExceeded(balance.current_balance, limit, order.total_price)

    order.status = target
    order.save(update_fields=("status", "updated_at"))
    OrderStatusHistory.objects.create(
        order=order,
        from_status=previous,
        status=target,
        actor=actor,
        note=reason[:500],
    )
    if target == Order.Status.CONFIRMED:
        entry = BalanceEntry.objects.create(
            company=order.company,
            shop=order.shop,
            amount=order.total_price,
            direction=BalanceEntry.Direction.DEBIT,
            order=order,
            note=f"Buyurtma #{order.pk} tasdiqlandi",
        )
        entry.post()
    elif target == Order.Status.CANCELLED and previous == Order.Status.CONFIRMED:
        entry = BalanceEntry.objects.create(
            company=order.company,
            shop=order.shop,
            amount=order.total_price,
            direction=BalanceEntry.Direction.CREDIT,
            order=order,
            note=f"Buyurtma #{order.pk} bekor qilindi",
        )
        entry.post()
    audit(actor, order.company, f"order.{target}", order, {"status": previous}, order_state(order))
    return order


class AdminPage(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class PageLinksSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)


class OrderAdminPageSerializer(PageLinksSerializer):
    results = ShopOrderSerializer(many=True)


class CompanyAdminViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    pagination_class = AdminPage

    @property
    def company(self):
        return company_for_request(self.request)

    def perform_create(self, serializer):
        instance = serializer.save(company=self.company)
        audit(self.request.user, self.company, "create", instance, after=snapshot(instance))

    def perform_update(self, serializer):
        instance = self.get_object()
        before = snapshot(instance)
        instance = serializer.save()
        audit(self.request.user, self.company, "update", instance, before, snapshot(instance))


class ProductAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id", "name", "image", "unit", "price", "unit_weight",
            "unit_volume", "is_active", "is_archived", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ProductAdminViewSet(
    CompanyAdminViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = Product.objects.all()
    serializer_class = ProductAdminSerializer

    def get_queryset(self):
        return Product.objects.filter(company=self.company).order_by("name")

    def perform_destroy(self, instance):
        before = {"is_active": instance.is_active, "is_archived": instance.is_archived}
        instance.is_active = False
        instance.is_archived = True
        instance.save(update_fields=("is_active", "is_archived", "updated_at"))
        audit(self.request.user, self.company, "archive", instance, before, {
            "is_active": False, "is_archived": True
        })


class ShopPriceAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopPrice
        fields = ("id", "shop", "product", "price", "discount_percent", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        company = company_for_request(self.context["request"])
        shop = attrs.get("shop", getattr(self.instance, "shop", None))
        product = attrs.get("product", getattr(self.instance, "product", None))
        if not CompanyShopLink.objects.filter(
            company=company, shop=shop, is_active=True
        ).exists():
            raise serializers.ValidationError({"shop": "Do‘kon kompaniyaga faol ulanmagan."})
        if product.company_id != company.pk:
            raise serializers.ValidationError({"product": "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."})
        return attrs


class ShopPriceAdminViewSet(
    CompanyAdminViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = ShopPrice.objects.all()
    serializer_class = ShopPriceAdminSerializer

    def get_queryset(self):
        return ShopPrice.objects.filter(company=self.company).select_related("shop", "product")

    def perform_destroy(self, instance):
        before = {"price": instance.price, "discount_percent": instance.discount_percent}
        instance.delete()
        audit(self.request.user, self.company, "delete", instance, before, None)


class VehicleAdminSerializer(serializers.ModelSerializer):
    capacity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = Vehicle
        fields = ("id", "name", "plate_number", "capacity", "is_active", "is_archived")
        read_only_fields = ("id",)


class VehicleAdminViewSet(
    CompanyAdminViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleAdminSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(company=self.company).order_by("plate_number")

    def perform_destroy(self, instance):
        before = {"is_active": instance.is_active, "is_archived": instance.is_archived}
        instance.is_active = False
        instance.is_archived = True
        instance.save(update_fields=("is_active", "is_archived", "updated_at"))
        audit(self.request.user, self.company, "archive", instance, before, {
            "is_active": False, "is_archived": True
        })


class ShopAdminSerializer(serializers.ModelSerializer):
    credit_limit = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
        required=False, allow_null=True,
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner", queryset=User.objects.filter(role=User.Role.SHOP_OWNER), write_only=True
    )
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)

    class Meta:
        model = Shop
        fields = (
            "id", "owner_id", "owner_phone", "name", "owner_name", "phone_primary",
            "phone_secondary", "address", "district", "latitude", "longitude",
            "status", "credit_limit",
        )
        read_only_fields = ("id", "owner_phone", "status")

    def create(self, validated_data):
        credit_limit = validated_data.pop("credit_limit", None)
        shop = super().create(validated_data)
        ShopBalance.objects.update_or_create(
            company=company_for_request(self.context["request"]),
            shop=shop,
            defaults={"credit_limit": credit_limit},
        )
        return shop

    def update(self, instance, validated_data):
        credit_limit = validated_data.pop("credit_limit", serializers.empty)
        shop = super().update(instance, validated_data)
        if credit_limit is not serializers.empty:
            ShopBalance.objects.update_or_create(
                company=company_for_request(self.context["request"]),
                shop=shop,
                defaults={"credit_limit": credit_limit},
            )
        return shop

    def to_representation(self, instance):
        data = super().to_representation(instance)
        balance = ShopBalance.objects.filter(
            company=company_for_request(self.context["request"]), shop=instance
        ).first()
        data["credit_limit"] = balance.credit_limit if balance else None
        return data

    def validate_owner_id(self, owner):
        if not self.instance and owner.shops.exists():
            raise serializers.ValidationError("Bu akkaunt allaqachon do‘konga biriktirilgan.")
        return owner


class ShopAdminViewSet(
    CompanyAdminViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
):
    queryset = Shop.objects.all()
    serializer_class = ShopAdminSerializer
    filter_backends = ()

    def get_queryset(self):
        return Shop.objects.filter(
            company_links__company=self.company,
            company_links__is_active=True,
        ).distinct().order_by("name")

    def perform_create(self, serializer):
        shop = serializer.save()
        CompanyShopLink.objects.create(company=self.company, shop=shop)
        audit(self.request.user, self.company, "create", shop, after={"id": shop.pk})

    def perform_update(self, serializer):
        before = {
            "name": serializer.instance.name,
            "status": serializer.instance.status,
            "credit_limit": ShopBalance.objects.filter(
                company=self.company, shop=serializer.instance
            ).values_list("credit_limit", flat=True).first(),
        }
        shop = serializer.save()
        audit(self.request.user, self.company, "update", shop, before, {
            "name": shop.name, "status": shop.status,
            "credit_limit": ShopBalance.objects.filter(
                company=self.company, shop=shop
            ).values_list("credit_limit", flat=True).first(),
        })

    @action(detail=True, methods=("post",))
    def archive(self, request, pk=None):
        shop = self.get_object()
        link = get_object_or_404(CompanyShopLink, shop=shop, company=self.company)
        was_active = link.is_active
        link.is_active = False
        link.save(update_fields=("is_active", "updated_at"))
        if not shop.company_links.filter(is_active=True).exists():
            shop.status = Shop.Status.ARCHIVED
            shop.save(update_fields=("status", "updated_at"))
        audit(request.user, self.company, "archive", shop, {"link_active": was_active}, {
            "link_active": False, "status": shop.status,
        })
        return Response({"status": shop.status})


class DriverAdminSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    blocked = serializers.BooleanField(source="user.is_blocked", read_only=True)

    class Meta:
        model = DriverProfile
        fields = ("id", "user", "phone", "license_number", "is_active", "blocked")
        read_only_fields = ("id", "user", "phone", "is_active", "blocked")


class DriverAdminViewSet(
    CompanyAdminViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = DriverProfile.objects.all()
    serializer_class = DriverAdminSerializer

    def get_queryset(self):
        return DriverProfile.objects.filter(company=self.company).select_related("user")

    def perform_destroy(self, instance):
        before = {"is_active": instance.user.is_active, "is_blocked": instance.user.is_blocked}
        instance.user.is_active = False
        instance.user.is_blocked = True
        instance.user.auth_version += 1
        instance.user.save(update_fields=("is_active", "is_blocked", "auth_version"))
        audit(self.request.user, self.company, "deactivate", instance, before, {
            "is_active": False, "is_blocked": True,
        })

    @action(detail=True, methods=("post",))
    def activate(self, request, pk=None):
        driver = self.get_object()
        before = {"is_active": driver.user.is_active, "is_blocked": driver.user.is_blocked}
        driver.user.is_active = True
        driver.user.is_blocked = False
        driver.user.auth_version += 1
        driver.user.save(update_fields=("is_active", "is_blocked", "auth_version"))
        audit(request.user, self.company, "activate", driver, before, {
            "is_active": True, "is_blocked": False,
        })
        return Response({"id": driver.pk, "is_active": True, "is_blocked": False})


class StaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=(User.Role.COMPANY_ADMIN, User.Role.DRIVER))

    class Meta:
        model = User
        fields = ("id", "phone", "role", "password", "is_active", "is_blocked")
        read_only_fields = ("id", "is_active", "is_blocked")

    def validate_phone(self, value):
        from apps.accounts.services import normalize_uz_phone
        return normalize_uz_phone(value)

    def validate_password(self, value):
        validate_password(value)
        return value

class StaffAdminViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    serializer_class = StaffSerializer
    lookup_value_regex = r"\d+"

    @property
    def company(self):
        return company_for_request(self.request)

    @extend_schema(responses=StaffSerializer(many=True))
    def list(self, request):
        users = User.objects.filter(company=self.company, role__in=(
            User.Role.COMPANY_ADMIN, User.Role.DRIVER
        ))
        return Response(StaffSerializer(users, many=True).data)

    @extend_schema(request=StaffSerializer, responses={201: StaffSerializer})
    def create(self, request):
        serializer = StaffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with transaction.atomic():
            user = User.objects.create_user(
                phone=values["phone"],
                password=values["password"],
                company=self.company,
                role=values["role"],
            )
            if user.role == User.Role.DRIVER:
                profile = DriverProfile(company=self.company, user=user)
                profile.full_clean()
                profile.save()
            audit(request.user, self.company, "create", user, after={
                "phone": user.phone, "role": user.role,
            })
        return Response(StaffSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("post",), url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = get_object_or_404(
            User.objects.filter(
                company=self.company, role__in=(User.Role.COMPANY_ADMIN, User.Role.DRIVER)
            ),
            pk=pk,
        )
        user.is_active = False
        user.is_blocked = True
        user.auth_version += 1
        user.save(update_fields=("is_active", "is_blocked", "auth_version"))
        audit(request.user, self.company, "deactivate", user, {"is_active": True}, {
            "is_active": False, "is_blocked": True,
        })
        return Response({"id": user.pk, "is_active": user.is_active, "is_blocked": user.is_blocked})

    @action(detail=True, methods=("post",), url_path="activate")
    def activate(self, request, pk=None):
        user = get_object_or_404(
            User.objects.filter(
                company=self.company, role__in=(User.Role.COMPANY_ADMIN, User.Role.DRIVER)
            ),
            pk=pk,
        )
        user.is_active = True
        user.is_blocked = False
        user.auth_version += 1
        user.save(update_fields=("is_active", "is_blocked", "auth_version"))
        audit(request.user, self.company, "activate", user, {"is_active": False}, {
            "is_active": True, "is_blocked": False,
        })
        return Response({"id": user.pk, "is_active": user.is_active, "is_blocked": user.is_blocked})


class OrderStatusInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    reason = serializers.CharField(max_length=500)
    allow_credit_limit_exceeded = serializers.BooleanField(required=False, default=False)


class BulkConfirmSerializer(serializers.Serializer):
    order_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1)
    reason = serializers.CharField(max_length=500)
    allow_credit_limit_exceeded = serializers.BooleanField(required=False, default=False)


class OrderAdminListQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    district = serializers.CharField(required=False, max_length=120)
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False)
    shop = serializers.IntegerField(min_value=1, required=False)
    search = serializers.CharField(required=False, allow_blank=True, max_length=200)


class PickingListQuerySerializer(serializers.Serializer):
    date = serializers.DateField()


class PickingListItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    unit = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_weight = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    total_volume = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )


class PickingListSerializer(serializers.Serializer):
    date = serializers.DateField()
    items = PickingListItemSerializer(many=True)


class BulkConfirmResponseSerializer(serializers.Serializer):
    confirmed = serializers.ListField(child=serializers.IntegerField())


class OrderAdminViewSet(viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    queryset = Order.objects.all()
    serializer_class = ShopOrderSerializer
    pagination_class = AdminPage
    lookup_value_regex = r"\d+"

    @property
    def company(self):
        return company_for_request(self.request)

    def get_queryset(self):
        return Order.objects.filter(company=self.company).select_related(
            "company", "shop"
        ).prefetch_related("items__product", "status_history__actor")

    @extend_schema(responses=OrderAdminPageSerializer)
    def list(self, request):
        orders = self.get_queryset()
        query_serializer = OrderAdminListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        if filters.get("date"):
            orders = orders.filter(delivery_date=filters["date"])
        if filters.get("status"):
            orders = orders.filter(status=filters["status"])
        if filters.get("shop"):
            orders = orders.filter(shop_id=filters["shop"])
        if filters.get("district"):
            orders = orders.filter(shop__district__iexact=filters["district"])
        query = filters.get("search", "").strip()
        if query:
            search_filter = (
                Q(shop__name__icontains=query)
                | Q(shop__phone_primary__icontains=query)
            )
            if query.isdecimal():
                search_filter |= Q(pk=int(query))
            orders = orders.filter(search_filter)
        paginator = AdminPage()
        page = paginator.paginate_queryset(orders, request, view=self)
        return paginator.get_paginated_response(ShopOrderSerializer(page, many=True).data)

    @extend_schema(responses=ShopOrderSerializer)
    def retrieve(self, request, pk=None):
        order = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(ShopOrderSerializer(order).data)

    @extend_schema(request=OrderStatusInputSerializer, responses=ShopOrderSerializer)
    @action(detail=True, methods=("post",), url_path="status")
    def change_status(self, request, pk=None):
        order = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = OrderStatusInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = transition_order(
            order=order,
            actor=request.user,
            target=serializer.validated_data["status"],
            reason=serializer.validated_data["reason"],
            allow_credit_limit_exceeded=serializer.validated_data["allow_credit_limit_exceeded"],
        )
        return Response(ShopOrderSerializer(order).data)

    @extend_schema(request=BulkConfirmSerializer, responses=BulkConfirmResponseSerializer)
    @action(detail=False, methods=("post",), url_path="bulk-confirm")
    def bulk_confirm(self, request):
        serializer = BulkConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        order_ids = values["order_ids"]
        if len(order_ids) != len(set(order_ids)):
            raise ValidationError({"order_ids": "Buyurtma ID sini takrorlamang."})
        orders = list(self.get_queryset().filter(pk__in=order_ids).order_by("pk"))
        if len(orders) != len(order_ids):
            raise ValidationError({"order_ids": "Buyurtmalardan biri topilmadi."})
        with transaction.atomic():
            for order in orders:
                transition_order(
                    order=order,
                    actor=request.user,
                    target=Order.Status.CONFIRMED,
                    reason=values["reason"],
                    allow_credit_limit_exceeded=values["allow_credit_limit_exceeded"],
                )
        return Response({"confirmed": order_ids})

    @extend_schema(responses=PickingListSerializer)
    @action(detail=False, methods=("get",), url_path="picking-list")
    def picking_list(self, request):
        query_serializer = PickingListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        delivery_date = query_serializer.validated_data["date"]
        orders = self.get_queryset().filter(
            delivery_date=delivery_date,
            status__in=(Order.Status.CONFIRMED, Order.Status.LOADED, Order.Status.IN_TRANSIT),
        )
        totals = {}
        for item in (
            orders
            .values("items__product_id", "items__product__name", "items__product__unit",
                    "items__product__unit_weight", "items__product__unit_volume")
            .annotate(quantity=Sum("items__quantity"))
        ):
            if item["items__product_id"] is None:
                continue
            product_id = item["items__product_id"]
            weight = item["items__product__unit_weight"]
            volume = item["items__product__unit_volume"]
            totals[product_id] = {
                "product_id": product_id,
                "product_name": item["items__product__name"],
                "unit": item["items__product__unit"],
                "quantity": item["quantity"],
                "total_weight": weight * item["quantity"] if weight is not None else None,
                "total_volume": volume * item["quantity"] if volume is not None else None,
            }
        return Response(PickingListSerializer({
            "date": delivery_date, "items": list(totals.values())
        }).data)


class PaymentInputSerializer(serializers.Serializer):
    shop_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    note = serializers.CharField(required=False, allow_blank=True)
    trip_id = serializers.IntegerField(required=False, min_value=1)


class PaymentOutputSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    shop_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.CharField()
    status = serializers.CharField()
    paid_at = serializers.DateTimeField(allow_null=True)
    reference = serializers.CharField()
    note = serializers.CharField()


class PaymentPageSerializer(PageLinksSerializer):
    results = PaymentOutputSerializer(many=True)


class PaymentAdminViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = PaymentOutputSerializer

    def _company(self):
        user = self.request.user
        if user.role not in (User.Role.SUPER_ADMIN, User.Role.COMPANY_ADMIN, User.Role.DRIVER):
            raise PermissionDenied("To‘lovni faqat kompaniya xodimi kiritishi mumkin.")
        return company_for_request(self.request)

    @extend_schema(responses=PaymentPageSerializer)
    def list(self, request):
        company = self._company()
        payments = Payment.objects.filter(company=company).select_related("shop")
        if request.user.role == User.Role.DRIVER:
            payments = payments.filter(
                shop__trip_stops__trip__driver__user=request.user
            ).distinct()
        paginator = AdminPage()
        page = paginator.paginate_queryset(payments, request, view=self)
        return paginator.get_paginated_response([
            {
                "id": payment.pk, "shop_id": payment.shop_id, "amount": payment.amount,
                "method": payment.method, "status": payment.status,
                "paid_at": payment.paid_at, "reference": payment.reference, "note": payment.note,
            }
            for payment in page
        ])

    @extend_schema(request=PaymentInputSerializer, responses={201: PaymentOutputSerializer})
    def create(self, request):
        company = self._company()
        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        shop = get_object_or_404(
            Shop.objects.filter(company_links__company=company, company_links__is_active=True),
            pk=values["shop_id"],
        )
        if request.user.role == User.Role.DRIVER:
            trip_id = values.get("trip_id")
            if not trip_id:
                raise ValidationError({"trip_id": "Haydovchi o‘z reysini ko‘rsatishi kerak."})
            assigned = Trip.objects.filter(
                pk=trip_id, company=company, driver__user=request.user
            ).filter(stops__shop=shop).exists()
            if not assigned:
                raise PermissionDenied("Do‘kon haydovchining reysiga kiritilmagan.")
        elif values.get("trip_id"):
            get_object_or_404(Trip, pk=values["trip_id"], company=company)

        with transaction.atomic():
            payment = Payment(
                company=company,
                shop=shop,
                amount=values["amount"],
                method=values["method"],
                status=Payment.Status.CONFIRMED,
                paid_at=timezone.now(),
                reference=values.get("reference", ""),
                note=values.get("note", ""),
            )
            payment.full_clean()
            payment.save()
            entry = BalanceEntry.objects.create(
                company=company,
                shop=shop,
                amount=payment.amount,
                direction=BalanceEntry.Direction.CREDIT,
                payment=payment,
                note=payment.note or f"To‘lov #{payment.pk}",
            )
            entry.post()
            audit(request.user, company, "create", payment, after={
                "shop_id": shop.pk, "amount": payment.amount, "method": payment.method,
            })
        return Response({
            "id": payment.pk, "shop_id": shop.pk, "amount": payment.amount,
            "method": payment.method, "status": payment.status, "paid_at": payment.paid_at,
            "reference": payment.reference, "note": payment.note,
        }, status=status.HTTP_201_CREATED)


class BalanceEntryOutputSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BalanceEntry
        fields = (
            "id", "company_id", "shop_id", "amount", "direction", "order_id",
            "payment_id", "note", "posted_at", "created_at",
        )


class ShopBalanceOutputSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    entries = serializers.SerializerMethodField()

    class Meta:
        model = ShopBalance
        fields = ("id", "company_id", "shop_id", "shop_name", "current_balance", "credit_limit", "entries")

    @extend_schema_field(BalanceEntryOutputSerializer(many=True))
    def get_entries(self, balance) -> list[dict]:
        rows = getattr(balance.shop, "company_balance_entries", None)
        if rows is None:
            rows = BalanceEntry.objects.filter(company=balance.company, shop=balance.shop)
        rows = [entry for entry in rows if entry.company_id == balance.company_id][:50]
        return BalanceEntryOutputSerializer(rows, many=True).data


class BalanceAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)
    queryset = ShopBalance.objects.all()
    serializer_class = ShopBalanceOutputSerializer
    pagination_class = AdminPage
    lookup_value_regex = r"\d+"

    @property
    def company(self):
        return company_for_request(self.request)

    def get_queryset(self):
        return ShopBalance.objects.filter(
            company=self.company,
            shop__company_links__company=self.company,
            shop__company_links__is_active=True,
        ).select_related("shop").order_by("shop__name", "pk").prefetch_related(
            Prefetch(
                "shop__balance_entries",
                queryset=BalanceEntry.objects.filter(company=self.company),
                to_attr="company_balance_entries",
            )
        )
