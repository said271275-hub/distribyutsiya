from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Product
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice
from apps.orders.models import Order, OrderItem, OrderStatusHistory


CENT = Decimal("0.01")


def ensure_order_window(company: Company, delivery_date) -> None:
    local_now = timezone.localtime()
    today = timezone.localdate(local_now)
    if delivery_date <= today:
        raise ValidationError({"delivery_date": "Yetkazish sanasi kamida ertangi kun bo‘lishi kerak."})
    if (
        delivery_date == today + timedelta(days=1)
        and local_now.time().replace(tzinfo=None) >= company.order_cutoff_time
    ):
        cutoff = company.order_cutoff_time.strftime("%H:%M")
        raise ValidationError(
            {"delivery_date": f"Ertangi yetkazish uchun buyurtma bugun soat {cutoff} gacha qabul qilinadi. Boshqa sanani tanlang."}
        )


def _get_price(shop: Shop, company: Company, product: Product) -> Decimal:
    shop_price = ShopPrice.objects.filter(
        shop=shop, company=company, product=product
    ).first()
    base = shop_price.price if shop_price and shop_price.price is not None else product.price
    discount = shop_price.discount_percent if shop_price else Decimal("0")
    return (base * (Decimal("100") - discount) / Decimal("100")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def _validated_items(shop: Shop, company: Company, items):
    if not items:
        raise ValidationError({"items": "Buyurtmada kamida bitta mahsulot bo‘lishi kerak."})
    product_ids = [item["product_id"] for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationError({"items": "Bir mahsulotni buyurtmada takrorlamang."})
    products = Product.objects.filter(
        pk__in=product_ids,
        company=company,
        is_active=True,
        is_archived=False,
    )
    product_map = {product.pk: product for product in products}
    if len(product_map) != len(product_ids):
        raise ValidationError({"items": "Mahsulot kompaniyada mavjud emas yoki faol emas."})
    return [
        (product_map[item["product_id"]], item["quantity"], _get_price(shop, company, product_map[item["product_id"]]))
        for item in items
    ]


def _replace_items(order: Order, priced_items) -> None:
    order.items.all().delete()
    for product, quantity, unit_price in priced_items:
        line_total = (quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
        OrderItem.objects.create(
            company=order.company,
            order=order,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
    order.recalculate_total()


@transaction.atomic
def create_shop_order(*, user, data, source_order=None) -> Order:
    shop = Shop.objects.select_for_update().get(owner=user)
    company_id = source_order.company_id if source_order else data["company_id"]
    link = (
        CompanyShopLink.objects.select_for_update()
        .select_related("company")
        .filter(shop=shop, company_id=company_id, is_active=True, company__is_active=True)
        .first()
    )
    if link is None:
        raise ValidationError({"company_id": "Bu kompaniya do‘kon uchun faol emas."})
    company = link.company
    ensure_order_window(company, data["delivery_date"])
    priced_items = _validated_items(shop, company, data["items"])
    order = Order.objects.create(
        company=company,
        shop=shop,
        delivery_date=data["delivery_date"],
        delivery_time_from=data.get("delivery_time_from"),
        delivery_time_to=data.get("delivery_time_to"),
        note=data.get("note", ""),
    )
    order.full_clean()
    _replace_items(order, priced_items)
    OrderStatusHistory.objects.create(order=order, status=order.status, actor=user)
    return order


@transaction.atomic
def update_shop_order(*, order: Order, user, data) -> Order:
    if order.status != Order.Status.NEW:
        raise ValidationError({"status": "Faqat tasdiqlanmagan buyurtmani tahrirlash mumkin."})
    company = order.company
    delivery_date = data.get("delivery_date", order.delivery_date)
    ensure_order_window(company, delivery_date)
    if "items" in data:
        priced_items = _validated_items(order.shop, company, data["items"])
    else:
        priced_items = None
    for field in ("delivery_date", "delivery_time_from", "delivery_time_to", "note"):
        if field in data:
            setattr(order, field, data[field])
    order.full_clean()
    order.save()
    if priced_items is not None:
        _replace_items(order, priced_items)
    return order


@transaction.atomic
def cancel_shop_order(*, order: Order, user, note: str = "") -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.NEW:
        raise ValidationError({"status": "Faqat admin tasdiqlamagan buyurtmani bekor qilish mumkin."})
    order.status = Order.Status.CANCELLED
    order.save(update_fields=("status", "updated_at"))
    OrderStatusHistory.objects.create(
        order=order, status=order.status, actor=user, note=note[:500]
    )
    return order