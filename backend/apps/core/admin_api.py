import json
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import F, Prefetch, Q, Sum
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
from apps.catalog.models import ContainerMovement, Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.core.inventory import (
    cancel_order_inventory,
    deliver_order_inventory,
    record_inventory_entry,
    reverse_inventory_entry,
)
from apps.core.models import InventoryEntry, ProductStock
from apps.core.permissions import CompanyAdminPermission, InventoryAdminPermission
from apps.logistics.models import DriverProfile, Trip, Vehicle
from apps.orders.models import Order, OrderStatusHistory
from apps.orders.sms_notifications import queue_order_sms
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
    Order.Status.CONFIRMED: {
        Order.Status.LOADED, Order.Status.CANCELLED,
    },
    Order.Status.LOADED: {Order.Status.IN_TRANSIT, Order.Status.CANCELLED},
    Order.Status.IN_TRANSIT: {Order.Status.DELIVERED, Order.Status.CANCELLED},
    Order.Status.DELIVERED: {Order.Status.CANCELLED},
    Order.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_order(
    *,
    order,
    actor,
    target,
    reason,
    allow_credit_limit_exceeded=False,
    delivered_items=None,
    notify_sms=True,
    inventory_trip=None,
):
    order = Order.objects.select_for_update().select_related("shop", "company").get(pk=order.pk)
    previous = order.status
    if target not in ORDER_TRANSITIONS.get(previous, set()):
        raise ValidationError({"status": f"{previous} holatidan {target} holatiga o‘tib bo‘lmaydi."})
    if not reason.strip():
        raise ValidationError({"reason": "Holat o‘zgarishi sababini kiriting."})

    delivery_total = Decimal("0.00")
    delivered_quantities = None
    if target == Order.Status.DELIVERED:
        items = list(order.items.select_for_update().order_by("pk"))
        if delivered_items is None:
            delivered_quantities = {item.pk: item.quantity for item in items}
        else:
            delivered_quantities = {
                item["item_id"]: item["quantity"] for item in delivered_items
            }
            if len(delivered_quantities) != len(delivered_items):
                raise ValidationError({"delivered_items": "Buyurtma bandini takrorlamang."})
            if set(delivered_quantities) != {item.pk for item in items}:
                raise ValidationError({
                    "delivered_items": "Har bir buyurtma bandi uchun yetkazilgan miqdorni yuboring."
                })

        for item in items:
            quantity = delivered_quantities[item.pk]
            if quantity > item.quantity:
                raise ValidationError({
                    "delivered_items": "Yetkazilgan miqdor buyurtma miqdoridan oshmasligi kerak."
                })
            item.delivered_quantity = quantity
            item.save(update_fields=("delivered_quantity", "updated_at"))
            delivery_total += (quantity * item.unit_price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        if not any(delivered_quantities.values()):
            raise ValidationError({
                "delivered_items": "Yetkazilgan mahsulot miqdori noldan katta bo‘lishi kerak."
            })

    if target == Order.Status.DELIVERED and delivery_total > 0:
        balance, _ = ShopBalance.objects.get_or_create(
            company=order.company, shop=order.shop
        )
        balance = ShopBalance.objects.select_for_update().get(pk=balance.pk)
        limit = balance.credit_limit
        projected = balance.current_balance + delivery_total
        if (
            limit is not None
            and projected > limit
            and not allow_credit_limit_exceeded
        ):
            raise CreditLimitExceeded(balance.current_balance, limit, delivery_total)

    order.status = target
    order.save(update_fields=("status", "updated_at"))
    OrderStatusHistory.objects.create(
        order=order,
        from_status=previous,
        status=target,
        actor=actor,
        note=reason[:500],
    )
    if target == Order.Status.DELIVERED:
        deliver_order_inventory(
            order=order,
            delivered_quantities=delivered_quantities,
            trip=inventory_trip,
        )
    if target == Order.Status.DELIVERED and delivery_total > 0:
        entry = BalanceEntry.objects.create(
            company=order.company,
            shop=order.shop,
            amount=delivery_total,
            direction=BalanceEntry.Direction.DEBIT,
            order=order,
            note=f"Buyurtma #{order.pk} yetkazildi",
        )
        entry.post()
    elif target == Order.Status.CANCELLED:
        debits = BalanceEntry.objects.filter(
            order=order,
            direction=BalanceEntry.Direction.DEBIT,
            posted_at__isnull=False,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        credits = BalanceEntry.objects.filter(
            order=order,
            direction=BalanceEntry.Direction.CREDIT,
            posted_at__isnull=False,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        reversal = debits - credits
        if reversal > 0:
            entry = BalanceEntry.objects.create(
                company=order.company,
                shop=order.shop,
                amount=reversal,
                direction=BalanceEntry.Direction.CREDIT,
                order=order,
                note=f"Buyurtma #{order.pk} bekor qilindi",
            )
            entry.post()
        cancel_order_inventory(order=order, reason=reason)
    audit(actor, order.company, f"order.{target}", order, {"status": previous}, order_state(order))
    if notify_sms and target == Order.Status.CONFIRMED:
        queue_order_sms(order, "confirmed")
    elif notify_sms and target == Order.Status.DELIVERED:
        queue_order_sms(order, "delivered")
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
    def get_fields(self):
        fields = super().get_fields()
        fields["image"].required = self.instance is None
        return fields

    def validate_image(self, image):
        if image.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Rasm hajmi 5 MB dan oshmasin.")
        return image

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
    volume_capacity = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Vehicle
        fields = (
            "id", "name", "plate_number", "capacity", "volume_capacity",
            "is_active", "is_archived",
        )
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
        company = company_for_request(self.context["request"])
        balance = ShopBalance.objects.filter(company=company, shop=instance).first()
        data["credit_limit"] = balance.credit_limit if balance else None
        link_active = CompanyShopLink.objects.filter(
            company=company, shop=instance, is_active=True
        ).exists()
        if not link_active:
            data["status"] = Shop.Status.ARCHIVED
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
        shops = Shop.objects.filter(company_links__company=self.company)
        shop_status = self.request.query_params.get("status")
        if shop_status == "archived":
            shops = shops.filter(company_links__is_active=False)
        elif shop_status in ("active", "inactive"):
            shops = shops.filter(
                company_links__is_active=True,
                status=shop_status,
            )
        elif shop_status != "all":
            shops = shops.filter(company_links__is_active=True)
        return shops.distinct().order_by("name")

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

    @action(detail=True, methods=("post",))
    @transaction.atomic
    def restore(self, request, pk=None):
        if request.user.role != User.Role.COMPANY_ADMIN:
            raise PermissionDenied("Do‘konni faqat o‘z kompaniyasining administratori tiklay oladi.")
        shop = get_object_or_404(
            Shop.objects.filter(company_links__company=self.company),
            pk=pk,
        )
        link = get_object_or_404(
            CompanyShopLink.objects.select_for_update(),
            shop=shop,
            company=self.company,
        )
        before = {
            "link_active": link.is_active,
            "status": shop.status,
        }
        link.is_active = True
        link.save(update_fields=("is_active", "updated_at"))
        shop.status = Shop.Status.ACTIVE
        shop.save(update_fields=("status", "updated_at"))
        audit(request.user, self.company, "restore", shop, before, {
            "link_active": True,
            "status": shop.status,
        })
        return Response({"status": shop.status})


class DriverAdminSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="user.phone", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    blocked = serializers.BooleanField(source="user.is_blocked", read_only=True)
    vehicle_id = serializers.PrimaryKeyRelatedField(
        source="vehicle",
        queryset=Vehicle.objects.all(),
        required=False,
        allow_null=True,
    )
    vehicle_name = serializers.CharField(source="vehicle.name", read_only=True, allow_null=True)

    class Meta:
        model = DriverProfile
        fields = (
            "id", "user", "phone", "license_number", "vehicle_id", "vehicle_name",
            "is_active", "blocked",
        )
        read_only_fields = ("id", "user", "phone", "is_active", "blocked")

    def validate(self, attrs):
        vehicle = attrs.get("vehicle")
        if vehicle is not None:
            company = self.context["company"]
            if vehicle.company_id != company.pk:
                raise serializers.ValidationError({
                    "vehicle_id": "Boshqa kompaniyaning transportini tanlab bo‘lmaydi."
                })
            current_vehicle_id = self.instance.vehicle_id if self.instance else None
            if (
                (not vehicle.is_active or vehicle.is_archived)
                and vehicle.pk != current_vehicle_id
            ):
                raise serializers.ValidationError({
                    "vehicle_id": "Yangi biriktirish uchun faqat faol transportni tanlash mumkin."
                })
        return attrs


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
        return DriverProfile.objects.filter(company=self.company).select_related(
            "user", "vehicle"
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = self.company
        return context

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
        phone = normalize_uz_phone(value)
        existing_users = User.objects.filter(phone=phone)
        if self.instance:
            existing_users = existing_users.exclude(pk=self.instance.pk)
        if existing_users.exists():
            raise serializers.ValidationError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")
        return phone

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

    def partial_update(self, request, pk=None):
        user = get_object_or_404(
            User.objects.filter(company=self.company, role=User.Role.COMPANY_ADMIN),
            pk=pk,
        )
        if user.pk == request.user.pk:
            raise ValidationError({"detail": "O‘z akkauntingizni xodimlar boshqaruvi orqali tahrirlay olmaysiz."})
        serializer = StaffUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = {"phone": user.phone, "role": user.role}
        user = serializer.save()
        audit(request.user, self.company, "update", user, before, {
            "phone": user.phone, "role": user.role,
        })
        return Response(StaffSerializer(user).data)

    @action(detail=True, methods=("post",), url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = get_object_or_404(
            User.objects.filter(company=self.company, role=User.Role.COMPANY_ADMIN),
            pk=pk,
        )
        if user.pk == request.user.pk:
            raise ValidationError({"detail": "O‘z parolingizni xodimlar boshqaruvi orqali tiklay olmaysiz."})
        serializer = StaffPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        before = {"auth_version": user.auth_version}
        user.set_password(serializer.validated_data["password"])
        user.auth_version += 1
        user.save(update_fields=("password", "auth_version"))
        audit(request.user, self.company, "reset_password", user, before, {
            "auth_version": user.auth_version,
        })
        return Response({"id": user.pk, "password_reset": True})

    @action(detail=True, methods=("post",), url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = get_object_or_404(
            User.objects.filter(
                company=self.company, role__in=(User.Role.COMPANY_ADMIN, User.Role.DRIVER)
            ),
            pk=pk,
        )
        if user.pk == request.user.pk:
            raise ValidationError({"detail": "O‘z akkauntingizni faolsizlantira olmaysiz."})
        if not user.is_active and user.is_blocked:
            return Response({"id": user.pk, "is_active": False, "is_blocked": True})
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
        if user.pk == request.user.pk:
            raise ValidationError({"detail": "O‘z akkauntingizni ushbu amal bilan faollashtira olmaysiz."})
        if user.is_active and not user.is_blocked:
            return Response({"id": user.pk, "is_active": True, "is_blocked": False})
        user.is_active = True
        user.is_blocked = False
        user.auth_version += 1
        user.save(update_fields=("is_active", "is_blocked", "auth_version"))
        audit(request.user, self.company, "activate", user, {"is_active": False}, {
            "is_active": True, "is_blocked": False,
        })
        return Response({"id": user.pk, "is_active": user.is_active, "is_blocked": user.is_blocked})


class StaffUpdateSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(max_length=20)

    class Meta:
        model = User
        fields = ("phone",)

    def validate_phone(self, value):
        from apps.accounts.services import normalize_uz_phone
        phone = normalize_uz_phone(value)
        if User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")
        return phone


class StaffPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Parollar bir-biriga mos kelmadi."
            })
        validate_password(attrs["password"])
        return attrs


class DeliveredItemInputSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00")
    )


class OrderStatusInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    reason = serializers.CharField(max_length=500)
    allow_credit_limit_exceeded = serializers.BooleanField(required=False, default=False)
    delivered_items = DeliveredItemInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if "delivered_items" in attrs and attrs["status"] != Order.Status.DELIVERED:
            raise serializers.ValidationError({
                "delivered_items": "Yetkazilgan miqdor faqat yetkazish holatida yuboriladi."
            })
        return attrs


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
            delivered_items=serializer.validated_data.get("delivered_items"),
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
    paid_at = serializers.DateField(required=False)
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
        return paginator.get_paginated_response(PaymentOutputSerializer([
            {
                "id": payment.pk, "shop_id": payment.shop_id, "amount": payment.amount,
                "method": payment.method, "status": payment.status,
                "paid_at": payment.paid_at, "reference": payment.reference, "note": payment.note,
            }
            for payment in page
        ], many=True).data)

    @extend_schema(request=PaymentInputSerializer, responses={201: PaymentOutputSerializer})
    def create(self, request):
        if request.user.role == User.Role.DRIVER:
            raise PermissionDenied("Haydovchi to‘lov kirita olmaydi.")
        company = self._company()
        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        shop = get_object_or_404(
            Shop.objects.filter(company_links__company=company, company_links__is_active=True),
            pk=values["shop_id"],
        )
        if values.get("trip_id"):
            get_object_or_404(Trip, pk=values["trip_id"], company=company)

        paid_at = (
            timezone.make_aware(datetime.combine(values["paid_at"], time.min))
            if "paid_at" in values else timezone.now()
        )
        with transaction.atomic():
            payment = Payment(
                company=company,
                shop=shop,
                amount=values["amount"],
                method=values["method"],
                status=Payment.Status.CONFIRMED,
                paid_at=paid_at,
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
        return Response(PaymentOutputSerializer({
            "id": payment.pk, "shop_id": shop.pk, "amount": payment.amount,
            "method": payment.method, "status": payment.status, "paid_at": payment.paid_at,
            "reference": payment.reference, "note": payment.note,
        }).data, status=status.HTTP_201_CREATED)


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
    last_payment_at = serializers.SerializerMethodField()
    container_deposit = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DecimalField(max_digits=18, decimal_places=2))
    def get_container_deposit(self, balance):
        total = ContainerMovement.objects.filter(
            company=balance.company, shop=balance.shop
        ).aggregate(
            total=Sum(F("quantity_delta") * F("container__deposit_amount"))
        )["total"]
        return format(total or Decimal("0.00"), ".2f")

    class Meta:
        model = ShopBalance
        fields = (
            "id", "company_id", "shop_id", "shop_name", "current_balance",
            "credit_limit", "last_payment_at", "container_deposit", "entries",
        )

    @extend_schema_field(BalanceEntryOutputSerializer(many=True))
    def get_entries(self, balance) -> list[dict]:
        rows = getattr(balance.shop, "company_balance_entries", None)
        if rows is None:
            rows = BalanceEntry.objects.filter(company=balance.company, shop=balance.shop)
        rows = [entry for entry in rows if entry.company_id == balance.company_id][:50]
        return BalanceEntryOutputSerializer(rows, many=True).data

    def get_last_payment_at(self, balance):
        rows = getattr(balance.shop, "company_balance_entries", None)
        if rows is None:
            rows = BalanceEntry.objects.filter(
                company=balance.company, shop=balance.shop
            ).select_related("payment")
        payment_dates = [
            entry.payment.paid_at or entry.payment.created_at
            for entry in rows
            if entry.company_id == balance.company_id and entry.payment_id
        ]
        latest = max(payment_dates, default=None)
        return timezone.localtime(latest).date().isoformat() if latest else None


class BalanceAdjustmentInputSerializer(serializers.Serializer):
    shop_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    direction = serializers.ChoiceField(choices=BalanceEntry.Direction.choices)
    note = serializers.CharField(trim_whitespace=True, max_length=500)

    def validate_note(self, value):
        if not value:
            raise serializers.ValidationError("Tuzatish sababini kiriting.")
        return value


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
                queryset=BalanceEntry.objects.filter(company=self.company).select_related("payment"),
                to_attr="company_balance_entries",
            )
        )

    @extend_schema(
        request=BalanceAdjustmentInputSerializer,
        responses={201: BalanceEntryOutputSerializer},
    )
    @action(detail=False, methods=("post",))
    @transaction.atomic
    def adjust(self, request):
        serializer = BalanceAdjustmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        shop = get_object_or_404(
            Shop.objects.filter(
                company_links__company=self.company,
                company_links__is_active=True,
            ),
            pk=values["shop_id"],
        )
        entry = BalanceEntry(
            company=self.company,
            shop=shop,
            amount=values["amount"],
            direction=values["direction"],
            note=f"Tuzatish: {values['note']}",
        )
        entry.full_clean()
        entry.save()
        entry.post()
        audit(request.user, self.company, "adjust", entry, after={
            "shop_id": shop.pk,
            "amount": entry.amount,
            "direction": entry.direction,
            "note": entry.note,
        })
        return Response(BalanceEntryOutputSerializer(entry).data, status=status.HTTP_201_CREATED)


class InventoryStockSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="pk", read_only=True)
    product_name = serializers.CharField(source="name", read_only=True)
    unit = serializers.CharField(read_only=True)
    current_quantity = serializers.SerializerMethodField()
    reserved_quantity = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()
    minimum_quantity = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "product_id",
            "product_name",
            "unit",
            "current_quantity",
            "reserved_quantity",
            "available_quantity",
            "minimum_quantity",
            "is_low_stock",
        )

    def _stock(self, product):
        stocks = getattr(product, "company_stock_records", ())
        return stocks[0] if stocks else None

    @extend_schema_field(serializers.CharField())
    def get_current_quantity(self, product):
        stock = self._stock(product)
        return format(stock.current_quantity if stock else Decimal("0.00"), ".2f")

    @extend_schema_field(serializers.CharField())
    def get_reserved_quantity(self, product):
        stock = self._stock(product)
        return format(stock.reserved_quantity if stock else Decimal("0.00"), ".2f")

    @extend_schema_field(serializers.CharField())
    def get_available_quantity(self, product):
        stock = self._stock(product)
        value = stock.current_quantity - stock.reserved_quantity if stock else Decimal("0.00")
        return format(value, ".2f")

    @extend_schema_field(serializers.CharField())
    def get_minimum_quantity(self, product):
        stock = self._stock(product)
        return format(stock.minimum_quantity if stock else Decimal("0.00"), ".2f")

    @extend_schema_field(serializers.BooleanField())
    def get_is_low_stock(self, product):
        stock = self._stock(product)
        return bool(
            stock
            and stock.minimum_quantity > 0
            and stock.current_quantity - stock.reserved_quantity <= stock.minimum_quantity
        )


class InventoryEntrySerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    unit = serializers.CharField(source="product.unit", read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    trip_id = serializers.IntegerField(read_only=True)
    reversal_of_id = serializers.IntegerField(read_only=True)
    reversal_id = serializers.SerializerMethodField()
    can_reverse = serializers.SerializerMethodField()

    class Meta:
        model = InventoryEntry
        fields = (
            "id",
            "product_id",
            "product_name",
            "unit",
            "entry_type",
            "quantity_delta",
            "reserved_delta",
            "batch_number",
            "reason",
            "occurred_at",
            "order_id",
            "trip_id",
            "reversal_of_id",
            "reversal_id",
            "can_reverse",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_reversal_id(self, entry):
        reversal = getattr(entry, "reversal", None)
        return reversal.pk if reversal else None

    @extend_schema_field(serializers.BooleanField())
    def get_can_reverse(self, entry):
        return (
            entry.order_id is None
            and entry.trip_id is None
            and entry.entry_type in (
                InventoryEntry.Type.RECEIPT,
                InventoryEntry.Type.ISSUE,
                InventoryEntry.Type.ADJUSTMENT,
            )
            and self.get_reversal_id(entry) is None
        )


class InventoryReceiptInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    batch_number = serializers.CharField(max_length=120, allow_blank=True, required=False)
    date = serializers.DateField()
    note = serializers.CharField(max_length=400, allow_blank=True, required=False)


class InventoryIssueInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01")
    )
    reason = serializers.CharField(trim_whitespace=True, max_length=400)

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("Chiqim sababini kiriting.")
        return value


INVENTORY_ADJUSTMENT_REASONS = (
    ("inventory", "Inventarizatsiya"),
    ("damaged", "Brak"),
    ("lost", "Yo‘qotish"),
)


class InventoryAdjustmentInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity_delta = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.ChoiceField(choices=INVENTORY_ADJUSTMENT_REASONS)
    note = serializers.CharField(max_length=400, allow_blank=True, required=False)

    def validate_quantity_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("Tuzatish miqdori noldan farqli bo‘lishi kerak.")
        return value


class InventoryMinimumInputSerializer(serializers.Serializer):
    minimum_quantity = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.00")
    )


class InventoryReverseInputSerializer(serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True, max_length=400)

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("Teskari yozuv sababini kiriting.")
        return value


class InventoryAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, InventoryAdminPermission)
    serializer_class = InventoryStockSerializer
    pagination_class = AdminPage
    lookup_value_regex = r"\d+"

    @property
    def company(self):
        return company_for_request(self.request)

    def get_queryset(self):
        company = self.company
        return Product.objects.filter(
            company=company, is_archived=False
        ).order_by("name", "pk").prefetch_related(
            Prefetch(
                "stock_records",
                queryset=ProductStock.objects.filter(company=company),
                to_attr="company_stock_records",
            )
        )

    @extend_schema(request=InventoryReceiptInputSerializer, responses={201: InventoryEntrySerializer})
    @action(detail=False, methods=("post",), url_path="receipt")
    @transaction.atomic
    def receipt(self, request):
        serializer = InventoryReceiptInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        product = get_object_or_404(
            Product.objects.filter(company=self.company, is_archived=False),
            pk=values["product_id"],
        )
        batch_number = values.get("batch_number", "").strip()
        note = values.get("note", "").strip()
        reason = "Kirim"
        if batch_number:
            reason += f", partiya {batch_number}"
        if note:
            reason += f": {note}"
        occurred_at = timezone.make_aware(
            datetime.combine(values["date"], time.min)
        )
        entry = record_inventory_entry(
            company=self.company,
            product=product,
            entry_type=InventoryEntry.Type.RECEIPT,
            quantity_delta=values["quantity"],
            batch_number=batch_number,
            reason=reason,
            occurred_at=occurred_at,
        )
        audit(request.user, self.company, "inventory.receipt", entry, after={
            "product_id": product.pk,
            "quantity": entry.quantity_delta,
            "batch_number": batch_number,
            "date": values["date"],
        })
        return Response(InventoryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=InventoryIssueInputSerializer, responses={201: InventoryEntrySerializer})
    @action(detail=False, methods=("post",), url_path="issue")
    @transaction.atomic
    def issue(self, request):
        serializer = InventoryIssueInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        product = get_object_or_404(
            Product.objects.filter(company=self.company, is_archived=False),
            pk=values["product_id"],
        )
        entry = record_inventory_entry(
            company=self.company,
            product=product,
            entry_type=InventoryEntry.Type.ISSUE,
            quantity_delta=-values["quantity"],
            reason=values["reason"],
        )
        audit(request.user, self.company, "inventory.issue", entry, after={
            "product_id": product.pk,
            "quantity": values["quantity"],
            "reason": entry.reason,
        })
        return Response(InventoryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=InventoryAdjustmentInputSerializer, responses={201: InventoryEntrySerializer})
    @action(detail=False, methods=("post",), url_path="adjustment")
    @transaction.atomic
    def adjustment(self, request):
        serializer = InventoryAdjustmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        product = get_object_or_404(
            Product.objects.filter(company=self.company, is_archived=False),
            pk=values["product_id"],
        )
        reason_label = dict(INVENTORY_ADJUSTMENT_REASONS)[values["reason"]]
        note = values.get("note", "").strip()
        reason = reason_label if not note else f"{reason_label}: {note}"
        entry = record_inventory_entry(
            company=self.company,
            product=product,
            entry_type=InventoryEntry.Type.ADJUSTMENT,
            quantity_delta=values["quantity_delta"],
            reason=reason,
        )
        audit(request.user, self.company, "inventory.adjustment", entry, after={
            "product_id": product.pk,
            "quantity_delta": entry.quantity_delta,
            "reason": entry.reason,
        })
        return Response(InventoryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=InventoryMinimumInputSerializer, responses=InventoryStockSerializer)
    @action(detail=True, methods=("patch",), url_path="minimum")
    @transaction.atomic
    def minimum(self, request, pk=None):
        product = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = InventoryMinimumInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = Product.objects.select_for_update().get(
            pk=product.pk, company=self.company
        )
        stock, _ = ProductStock.objects.get_or_create(
            company=self.company, product=product
        )
        stock = ProductStock.objects.select_for_update().get(pk=stock.pk)
        before = stock.minimum_quantity
        stock.minimum_quantity = serializer.validated_data["minimum_quantity"]
        stock.save(update_fields=("minimum_quantity", "updated_at"))
        audit(request.user, self.company, "inventory.minimum", stock, {
            "minimum_quantity": before,
        }, {
            "minimum_quantity": stock.minimum_quantity,
        })
        product.company_stock_records = [stock]
        return Response(InventoryStockSerializer(product).data)


class InventoryEntryAdminViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, InventoryAdminPermission)
    queryset = InventoryEntry.objects.all()
    serializer_class = InventoryEntrySerializer
    pagination_class = AdminPage
    lookup_value_regex = r"\d+"

    @property
    def company(self):
        return company_for_request(self.request)

    def get_queryset(self):
        queryset = InventoryEntry.objects.filter(
            company=self.company
        ).select_related("product", "order", "trip", "reversal_of").prefetch_related("reversal")
        product_id = self.request.query_params.get("product_id")
        if product_id:
            try:
                product_id = int(product_id)
            except ValueError as error:
                raise ValidationError({"product_id": "Mahsulot raqami noto‘g‘ri."}) from error
            queryset = queryset.filter(product_id=product_id)
        return queryset

    @extend_schema(request=InventoryReverseInputSerializer, responses={201: InventoryEntrySerializer})
    @action(detail=True, methods=("post",), url_path="reverse")
    @transaction.atomic
    def reverse(self, request, pk=None):
        serializer = InventoryReverseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        original = get_object_or_404(self.get_queryset(), pk=pk)
        entry = reverse_inventory_entry(
            company=self.company,
            entry_id=original.pk,
            reason=serializer.validated_data["reason"],
        )
        audit(request.user, self.company, "inventory.reverse", entry, after={
            "reversal_of_id": original.pk,
            "reason": entry.reason,
        })
        return Response(InventoryEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
