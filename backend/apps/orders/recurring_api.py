from datetime import timedelta
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.companies.models import CompanyShopLink, Shop
from apps.core.permissions import ShopOwnerPermission
from apps.orders.models import (
    RecurringOrderDraft,
    RecurringOrderSchedule,
)
from apps.orders.recurring_services import (
    MAX_ITEM_QUANTITY,
    MAX_ITEMS_PER_SCHEDULE,
    cancel_draft,
    confirm_draft,
    create_schedule,
    update_schedule,
)


class RecurringItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=MAX_ITEM_QUANTITY,
    )


class RecurringScheduleWriteSerializer(serializers.Serializer):
    company_id = serializers.IntegerField(min_value=1, required=False)
    name = serializers.CharField(max_length=120, required=False)
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        min_length=1,
        max_length=7,
        required=False,
    )
    delivery_time_from = serializers.TimeField(required=False, allow_null=True)
    delivery_time_to = serializers.TimeField(required=False, allow_null=True)
    items = RecurringItemInputSerializer(many=True, min_length=1, max_length=MAX_ITEMS_PER_SCHEDULE, required=False)

    def validate_weekdays(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Hafta kunini takrorlamang.")
        return value

    def validate(self, attrs):
        if not self.partial:
            required = ("company_id", "name", "weekdays", "items")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError({
                    field: "Bu maydon majburiy." for field in missing
                })
        if (
            attrs.get("delivery_time_from")
            and attrs.get("delivery_time_to")
            and attrs["delivery_time_from"] >= attrs["delivery_time_to"]
        ):
            raise serializers.ValidationError({
                "delivery_time_to": "Yetkazish oralig‘i boshlanishdan keyin tugashi kerak."
            })
        if "items" in attrs:
            ids = [row["product_id"] for row in attrs["items"]]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({"items": "Bir mahsulotni jadvalda takrorlamang."})
        return attrs


def _next_dates(schedule, today=None):
    today = today or timezone.localdate()
    return [
        (today + timedelta(days=offset)).isoformat()
        for offset in range(1, 8)
        if (today + timedelta(days=offset)).weekday() in schedule.weekdays
    ]


def _schedule_data(schedule):
    return {
        "id": schedule.pk,
        "company_id": schedule.company_id,
        "company_name": schedule.company.name,
        "name": schedule.name,
        "weekdays": schedule.weekdays,
        "delivery_time_from": (
            schedule.delivery_time_from.strftime("%H:%M")
            if schedule.delivery_time_from else None
        ),
        "delivery_time_to": (
            schedule.delivery_time_to.strftime("%H:%M")
            if schedule.delivery_time_to else None
        ),
        "is_active": schedule.is_active,
        "is_archived": schedule.is_archived,
        "items": [
            {
                "product_id": row.product_id,
                "product_name": row.product.name,
                "unit": row.product.unit,
                "quantity": str(row.quantity),
                "is_available": row.product.is_active and not row.product.is_archived,
            }
            for row in schedule.items.select_related("product").all()
        ],
        "next_dates": _next_dates(schedule) if schedule.is_active and not schedule.is_archived else [],
    }


def _draft_data(draft):
    return {
        "id": draft.pk,
        "schedule_id": draft.schedule_id,
        "schedule_name": draft.schedule.name,
        "company_name": draft.company.name,
        "delivery_date": draft.delivery_date.isoformat(),
        "status": draft.status,
        "order_id": draft.order_id,
        "items": [
            {
                "product_id": row.product_id,
                "product_name": row.product.name,
                "unit": row.product.unit,
                "quantity": str(row.quantity),
                "is_available": row.product.is_active and not row.product.is_archived,
            }
            for row in draft.items.select_related("product").all()
        ],
        "skipped_products": draft.skipped_products,
    }


class ShopRecurringBaseView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)

    def get_shop(self, user):
        return get_object_or_404(Shop, owner=user)


class ShopRecurringOrdersView(ShopRecurringBaseView):
    def get(self, request):
        shop = self.get_shop(request.user)
        schedules = (
            RecurringOrderSchedule.objects.filter(shop=shop)
            .select_related("company")
            .prefetch_related("items__product")
        )
        drafts = (
            RecurringOrderDraft.objects.filter(schedule__shop=shop)
            .select_related("schedule", "company", "order")
            .prefetch_related("items__product")
            .order_by("-delivery_date", "-pk")[:60]
        )
        links = CompanyShopLink.objects.filter(
            shop=shop,
            is_active=True,
            company__is_active=True,
        ).select_related("company").order_by("company__name")
        companies = []
        for link in links:
            products = Product.objects.filter(
                company_id=link.company_id,
                is_active=True,
                is_archived=False,
            ).order_by("name")
            companies.append({
                "id": link.company_id,
                "name": link.company.name,
                "products": [
                    {"id": product.pk, "name": product.name, "unit": product.unit}
                    for product in products
                ],
            })
        return Response({
            "schedules": [_schedule_data(row) for row in schedules],
            "drafts": [_draft_data(row) for row in drafts],
            "companies": companies,
        })

    def post(self, request):
        serializer = RecurringScheduleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        schedule = create_schedule(
            shop=self.get_shop(request.user),
            company_id=data["company_id"],
            data=data,
        )
        return Response(_schedule_data(schedule), status=201)


class ShopRecurringScheduleDetailView(ShopRecurringBaseView):
    def get_schedule(self, user, pk):
        return get_object_or_404(
            RecurringOrderSchedule.objects.select_related("company").prefetch_related(
                "items__product"
            ),
            pk=pk,
            shop__owner=user,
        )

    def patch(self, request, pk):
        schedule = self.get_schedule(request.user, pk)
        serializer = RecurringScheduleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "company_id" in serializer.validated_data:
            raise ValidationError({"company_id": "Jadval kompaniyasini o‘zgartirib bo‘lmaydi."})
        schedule = update_schedule(schedule=schedule, data=serializer.validated_data)
        return Response(_schedule_data(schedule))

    def get(self, request, pk):
        return Response(_schedule_data(self.get_schedule(request.user, pk)))


class ShopRecurringScheduleActionView(ShopRecurringBaseView):
    def post(self, request, pk, action):
        schedule = get_object_or_404(
            RecurringOrderSchedule.objects.select_related("company"),
            pk=pk,
            shop__owner=request.user,
        )
        if schedule.is_archived:
            raise ValidationError({"schedule": "Jadval allaqachon arxivlangan."})
        if action == "archive":
            schedule.is_archived = True
            schedule.is_active = False
        elif action == "pause":
            schedule.is_active = False
        elif action == "resume":
            schedule.is_active = True
        else:
            raise ValidationError({"action": "Jadval amali noto‘g‘ri."})
        schedule.save(update_fields=("is_archived", "is_active", "updated_at"))
        return Response(_schedule_data(schedule))


class ShopRecurringDraftActionView(ShopRecurringBaseView):
    def get_draft(self, user, pk):
        return get_object_or_404(
            RecurringOrderDraft.objects.select_related(
                "schedule__shop", "company"
            ).prefetch_related("items__product"),
            pk=pk,
            schedule__shop__owner=user,
        )

    def post(self, request, pk, action):
        draft = self.get_draft(request.user, pk)
        if action == "confirm":
            draft = confirm_draft(draft=draft, user=request.user)
        elif action == "cancel":
            draft = cancel_draft(draft=draft)
        else:
            raise ValidationError({"action": "Qoralama amali noto‘g‘ri."})
        return Response(_draft_data(draft))
