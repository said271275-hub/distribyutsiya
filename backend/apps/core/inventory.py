from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Product
from apps.core.models import InventoryEntry, ProductStock
from apps.orders.models import OrderItem


ZERO = Decimal("0.00")


@transaction.atomic
def record_inventory_entry(
    *,
    company,
    product,
    entry_type,
    quantity_delta=ZERO,
    reserved_delta=ZERO,
    batch_number="",
    reason="",
    occurred_at=None,
    order=None,
    order_item=None,
    trip=None,
    idempotency_key="",
    reversal_of=None,
):
    quantity_delta = Decimal(quantity_delta)
    reserved_delta = Decimal(reserved_delta)
    locked_product = Product.objects.select_for_update().get(
        pk=getattr(product, "pk", product), company_id=company.pk
    )

    if idempotency_key:
        existing = InventoryEntry.objects.filter(
            company=company, idempotency_key=idempotency_key
        ).first()
        if existing:
            same_payload = (
                existing.product_id == locked_product.pk
                and existing.entry_type == entry_type
                and existing.quantity_delta == quantity_delta
                and existing.reserved_delta == reserved_delta
                and existing.order_id == getattr(order, "pk", None)
                and existing.order_item_id == getattr(order_item, "pk", None)
                and existing.trip_id == getattr(trip, "pk", None)
                and existing.reversal_of_id == getattr(reversal_of, "pk", None)
            )
            if not same_payload:
                raise ValidationError({
                    "idempotency_key": "Bu amal identifikatori boshqa yozuv uchun ishlatilgan."
                })
            return existing

    stock, _ = ProductStock.objects.get_or_create(
        company=company, product=locked_product
    )
    stock = ProductStock.objects.select_for_update().get(pk=stock.pk)
    if stock.reserved_quantity + reserved_delta < ZERO:
        raise ValidationError({"stock": "Zaxiradagi miqdor manfiy bo‘lishi mumkin emas."})

    entry = InventoryEntry(
        company=company,
        product=locked_product,
        entry_type=entry_type,
        quantity_delta=quantity_delta,
        reserved_delta=reserved_delta,
        batch_number=batch_number,
        reason=reason,
        occurred_at=occurred_at or timezone.now(),
        order=order,
        order_item=order_item,
        trip=trip,
        idempotency_key=idempotency_key,
        reversal_of=reversal_of,
    )
    entry.full_clean()
    entry.save()
    ProductStock.objects.filter(pk=stock.pk).update(
        current_quantity=F("current_quantity") + quantity_delta,
        reserved_quantity=F("reserved_quantity") + reserved_delta,
        updated_at=timezone.now(),
    )
    return entry


@transaction.atomic
def reserve_order_inventory(*, order, trip):
    items = list(OrderItem.objects.select_for_update().filter(order=order).order_by("pk"))
    entries = []
    for item in items:
        entries.append(record_inventory_entry(
            company=order.company,
            product=item.product_id,
            entry_type=InventoryEntry.Type.RESERVATION,
            reserved_delta=item.quantity,
            reason=f"Reys #{trip.pk} tasdiqlandi",
            order=order,
            order_item=item,
            trip=trip,
            idempotency_key=f"trip:{trip.pk}:order:{order.pk}:reserve:{item.pk}",
        ))
    return entries


@transaction.atomic
def deliver_order_inventory(*, order, delivered_quantities, trip=None):
    items = list(OrderItem.objects.select_for_update().filter(order=order).order_by("pk"))
    entries = []
    for item in items:
        quantity = Decimal(delivered_quantities[item.pk])
        reserved = InventoryEntry.objects.filter(
            order_item=item
        ).aggregate(total=Sum("reserved_delta"))["total"] or ZERO
        reserved_delta = -reserved if reserved > ZERO else ZERO
        if quantity == ZERO and reserved_delta == ZERO:
            continue
        entries.append(record_inventory_entry(
            company=order.company,
            product=item.product_id,
            entry_type=InventoryEntry.Type.DELIVERY,
            quantity_delta=-quantity,
            reserved_delta=reserved_delta,
            reason=f"Buyurtma #{order.pk} yetkazildi",
            order=order,
            order_item=item,
            trip=trip,
            idempotency_key=f"order:{order.pk}:delivery:{item.pk}",
        ))
    return entries


@transaction.atomic
def cancel_order_inventory(*, order, reason):
    items = list(OrderItem.objects.select_for_update().filter(order=order).order_by("pk"))
    entries = []
    for item in items:
        totals = InventoryEntry.objects.filter(order_item=item).aggregate(
            quantity=Sum("quantity_delta"),
            reserved=Sum("reserved_delta"),
        )
        quantity = totals["quantity"] or ZERO
        reserved = totals["reserved"] or ZERO
        if quantity == ZERO and reserved == ZERO:
            continue
        entries.append(record_inventory_entry(
            company=order.company,
            product=item.product_id,
            entry_type=InventoryEntry.Type.REVERSAL,
            quantity_delta=-quantity,
            reserved_delta=-reserved,
            reason=f"Buyurtma #{order.pk} bekor qilindi: {reason}"[:500],
            order=order,
            order_item=item,
            idempotency_key=f"order:{order.pk}:cancellation:{item.pk}",
        ))
    return entries


@transaction.atomic
def release_trip_inventory(*, trip, order):
    items = list(OrderItem.objects.select_for_update().filter(order=order).order_by("pk"))
    entries = []
    for item in items:
        reserved = InventoryEntry.objects.filter(
            order_item=item
        ).aggregate(total=Sum("reserved_delta"))["total"] or ZERO
        if reserved <= ZERO:
            continue
        entries.append(record_inventory_entry(
            company=order.company,
            product=item.product_id,
            entry_type=InventoryEntry.Type.RELEASE,
            reserved_delta=-reserved,
            reason=f"Reys #{trip.pk} bekor qilindi",
            order=order,
            order_item=item,
            trip=trip,
            idempotency_key=f"trip:{trip.pk}:order:{order.pk}:release:{item.pk}",
        ))
    return entries


@transaction.atomic
def reverse_inventory_entry(*, company, entry_id, reason):
    original = InventoryEntry.objects.select_for_update().filter(
        company=company, pk=entry_id
    ).first()
    if original is None:
        raise ValidationError({"entry_id": "Ombor yozuvi topilmadi."})
    if original.order_id or original.trip_id or original.entry_type in (
        InventoryEntry.Type.RESERVATION,
        InventoryEntry.Type.DELIVERY,
        InventoryEntry.Type.RELEASE,
        InventoryEntry.Type.REVERSAL,
    ):
        raise ValidationError({
            "entry_id": "Reys yoki buyurtma yozuvini qo‘lda teskari yozib bo‘lmaydi."
        })
    if InventoryEntry.objects.filter(reversal_of=original).exists():
        raise ValidationError({"entry_id": "Bu yozuv allaqachon teskari yozilgan."})
    return record_inventory_entry(
        company=company,
        product=original.product_id,
        entry_type=InventoryEntry.Type.REVERSAL,
        quantity_delta=-original.quantity_delta,
        reserved_delta=-original.reserved_delta,
        batch_number=original.batch_number,
        reason=reason,
        reversal_of=original,
        idempotency_key=f"entry:{original.pk}:reversal",
    )
