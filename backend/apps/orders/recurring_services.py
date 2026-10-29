from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Product
from apps.companies.models import CompanyShopLink, Shop
from apps.orders.models import (
    RecurringOrderDraft,
    RecurringOrderDraftItem,
    RecurringOrderSchedule,
    RecurringOrderScheduleItem,
)
from apps.orders.shop_services import create_shop_order
from apps.orders.sms_notifications import queue_recurring_draft_sms

MAX_SCHEDULES_PER_SHOP = 10
MAX_ITEMS_PER_SCHEDULE = 50
MAX_ITEM_QUANTITY = Decimal("10000.00")
DRAFT_HORIZON_DAYS = 7


def _validate_schedule_items(company_id, items):
    if not items or len(items) > MAX_ITEMS_PER_SCHEDULE:
        raise ValidationError({"items": "Jadvalda 1 tadan 50 tagacha mahsulot bo‘lishi kerak."})
    product_ids = [item["product_id"] for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationError({"items": "Bir mahsulotni jadvalda takrorlamang."})
    product_count = Product.objects.filter(
        pk__in=product_ids,
        company_id=company_id,
        is_active=True,
        is_archived=False,
    ).count()
    if product_count != len(product_ids):
        raise ValidationError({"items": "Faqat faol va shu kompaniyaga tegishli mahsulotlarni tanlang."})
    for item in items:
        if item["quantity"] <= 0 or item["quantity"] > MAX_ITEM_QUANTITY:
            raise ValidationError({"items": "Mahsulot miqdori 0 dan katta va 10000 dan oshmasligi kerak."})


def _replace_schedule_items(schedule, items):
    _validate_schedule_items(schedule.company_id, items)
    schedule.items.all().delete()
    for item in items:
        RecurringOrderScheduleItem.objects.create(
            company_id=schedule.company_id,
            schedule=schedule,
            product_id=item["product_id"],
            quantity=item["quantity"],
        )


@transaction.atomic
def create_schedule(*, shop, company_id, data):
    Shop.objects.select_for_update().get(pk=shop.pk)
    link = CompanyShopLink.objects.filter(
        shop=shop,
        company_id=company_id,
        is_active=True,
        company__is_active=True,
    ).first()
    if link is None:
        raise ValidationError({"company_id": "Bu kompaniya do‘kon uchun faol emas."})
    active_count = RecurringOrderSchedule.objects.filter(
        shop=shop, is_archived=False
    ).count()
    if active_count >= MAX_SCHEDULES_PER_SHOP:
        raise ValidationError({"schedule": "Do‘kon uchun ko‘pi bilan 10 ta jadval yarating."})
    schedule = RecurringOrderSchedule.objects.create(
        company_id=company_id,
        shop=shop,
        name=data["name"],
        weekdays=data["weekdays"],
        delivery_time_from=data.get("delivery_time_from"),
        delivery_time_to=data.get("delivery_time_to"),
    )
    schedule.full_clean()
    _replace_schedule_items(schedule, data["items"])
    return schedule


@transaction.atomic
def update_schedule(*, schedule, data):
    schedule = RecurringOrderSchedule.objects.select_for_update().get(pk=schedule.pk)
    if schedule.is_archived:
        raise ValidationError({"schedule": "Arxivlangan jadvalni tahrirlab bo‘lmaydi."})
    if "items" in data:
        _replace_schedule_items(schedule, data["items"])
    for field in ("name", "weekdays", "delivery_time_from", "delivery_time_to"):
        if field in data:
            setattr(schedule, field, data[field])
    schedule.full_clean()
    schedule.save()
    getattr(schedule, "_prefetched_objects_cache", {}).pop("items", None)
    return schedule


def _create_draft(schedule, delivery_date):
    try:
        with transaction.atomic():
            draft, created = RecurringOrderDraft.objects.get_or_create(
                schedule=schedule,
                delivery_date=delivery_date,
                defaults={
                    "company_id": schedule.company_id,
                },
            )
    except IntegrityError:
        return False
    if not created:
        return False

    active_items = []
    skipped_products = []
    for item in schedule.items.select_related("product").all():
        product = item.product
        if not product.is_active or product.is_archived or product.company_id != schedule.company_id:
            skipped_products.append({"id": product.pk, "name": product.name})
            continue
        active_items.append(item)

    RecurringOrderDraft.objects.filter(pk=draft.pk).update(
        skipped_products=skipped_products
    )
    RecurringOrderDraftItem.objects.bulk_create([
        RecurringOrderDraftItem(
            company_id=schedule.company_id,
            draft=draft,
            product_id=item.product_id,
            quantity=item.quantity,
        )
        for item in active_items
    ])
    queue_recurring_draft_sms(draft)
    return True


@transaction.atomic
def create_recurring_drafts(*, today=None):
    today = today or timezone.localdate()
    RecurringOrderDraft.objects.filter(
        status=RecurringOrderDraft.Status.PENDING,
        delivery_date__lte=today,
    ).update(status=RecurringOrderDraft.Status.EXPIRED)

    created_count = 0
    schedules = (
        RecurringOrderSchedule.objects.filter(
            is_active=True,
            is_archived=False,
            shop__status=Shop.Status.ACTIVE,
            company__is_active=True,
            shop__company_links__is_active=True,
        )
        .select_related("company", "shop")
        .prefetch_related("items__product")
        .distinct()
    )
    for schedule in schedules:
        if not CompanyShopLink.objects.filter(
            company_id=schedule.company_id,
            shop_id=schedule.shop_id,
            is_active=True,
            company__is_active=True,
        ).exists():
            continue
        for offset in range(1, DRAFT_HORIZON_DAYS + 1):
            delivery_date = today + timedelta(days=offset)
            if delivery_date.weekday() in schedule.weekdays:
                created_count += int(_create_draft(schedule, delivery_date))
    return created_count


@transaction.atomic
def confirm_draft(*, draft, user):
    draft = (
        RecurringOrderDraft.objects.select_for_update()
        .select_related("schedule__shop", "company")
        .get(pk=draft.pk)
    )
    if draft.status != RecurringOrderDraft.Status.PENDING:
        raise ValidationError({"status": "Faqat tasdiq kutilayotgan qoralamani tasdiqlash mumkin."})
    if draft.delivery_date <= timezone.localdate():
        raise ValidationError({"status": "Qoralama muddati o‘tgan."})
    if not CompanyShopLink.objects.filter(
        shop=draft.schedule.shop,
        company=draft.company,
        is_active=True,
        company__is_active=True,
    ).exists():
        raise ValidationError({"company_id": "Bu kompaniya do‘kon uchun faol emas."})

    active_items = []
    skipped = list(draft.skipped_products)
    skipped_ids = {row["id"] for row in skipped}
    for item in draft.items.select_related("product").all():
        if not item.product.is_active or item.product.is_archived:
            if item.product_id not in skipped_ids:
                skipped.append({"id": item.product_id, "name": item.product.name})
                skipped_ids.add(item.product_id)
            continue
        active_items.append(item)
    draft.skipped_products = skipped
    draft.save(update_fields=("skipped_products", "updated_at"))
    if not active_items:
        raise ValidationError({"items": "Faol mahsulot qolmagani uchun qoralamani tasdiqlab bo‘lmadi."})

    order = create_shop_order(
        user=user,
        data={
            "company_id": draft.company_id,
            "delivery_date": draft.delivery_date,
            "delivery_time_from": draft.schedule.delivery_time_from,
            "delivery_time_to": draft.schedule.delivery_time_to,
            "items": [
                {"product_id": item.product_id, "quantity": item.quantity}
                for item in active_items
            ],
        },
    )
    draft.status = RecurringOrderDraft.Status.CONFIRMED
    draft.order = order
    draft.save(update_fields=("status", "order", "updated_at"))
    return draft


@transaction.atomic
def cancel_draft(*, draft):
    draft = RecurringOrderDraft.objects.select_for_update().get(pk=draft.pk)
    if draft.status != RecurringOrderDraft.Status.PENDING:
        raise ValidationError({"status": "Faqat tasdiq kutilayotgan qoralamani bekor qilish mumkin."})
    draft.status = RecurringOrderDraft.Status.CANCELLED
    draft.save(update_fields=("status", "updated_at"))
    return draft
