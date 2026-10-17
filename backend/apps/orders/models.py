from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import CompanyOwnedModel
from apps.companies.models import CompanyShopLink


class Order(CompanyOwnedModel):
    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        CONFIRMED = "confirmed", "Tasdiqlandi"
        LOADED = "loaded", "Yuklandi"
        IN_TRANSIT = "in_transit", "Yo‘lda"
        DELIVERED = "delivered", "Yetkazildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    delivery_date = models.DateField()
    delivery_time_from = models.TimeField(null=True, blank=True)
    delivery_time_to = models.TimeField(null=True, blank=True)
    total_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("company", "status", "delivery_date"))]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_price__gte=0), name="order_total_nonnegative"
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.shop_id and not CompanyShopLink.objects.filter(
            company_id=self.company_id, shop_id=self.shop_id, is_active=True
        ).exists():
            errors["shop"] = "Do‘kon faol kompaniya bilan bog‘lanmagan."
        if (
            self.delivery_time_from
            and self.delivery_time_to
            and self.delivery_time_from >= self.delivery_time_to
        ):
            errors["delivery_time_to"] = "Yetkazish oralig‘i boshlanishdan keyin tugashi kerak."
        if errors:
            raise ValidationError(errors)

    def recalculate_total(self):
        total = sum(item.line_total for item in self.items.all())
        self.total_price = total
        self.save(update_fields=("total_price", "updated_at"))


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="status_history"
    )
    from_status = models.CharField(max_length=12, choices=Order.Status.choices, null=True, blank=True)
    status = models.CharField(max_length=12, choices=Order.Status.choices)
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class OrderItem(CompanyOwnedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2, validators=(MinValueValidator(Decimal("0.01")),)
    )
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=(MinValueValidator(0),)
    )
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="order_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0, line_total__gte=0),
                name="order_item_prices_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id and self.order.company_id != self.company_id:
            errors["order"] = "Buyurtma shu kompaniyaga tegishli bo‘lishi kerak."
        if self.product_id and self.product.company_id != self.company_id:
            errors["product"] = "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."
        if self.quantity is not None and self.unit_price is not None:
            expected_total = self.quantity * self.unit_price
            self.line_total = expected_total
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.quantity is not None and self.unit_price is not None:
            self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
