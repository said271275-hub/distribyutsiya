from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CompanyOwnedModel(TimestampedModel):
    company = models.ForeignKey("companies.Company", on_delete=models.PROTECT)

    class Meta:
        abstract = True


class ProductStock(CompanyOwnedModel):
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="stock_records"
    )
    current_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reserved_quantity = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    minimum_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=(MinValueValidator(0),),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "product"), name="uniq_product_stock_company"
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name="product_stock_reserved_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_quantity__gte=0),
                name="product_stock_minimum_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.product_id and self.product.company_id != self.company_id:
            raise ValidationError({"product": "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."})


class InventoryEntryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError("Ombor harakatlari jurnalini tahrirlab bo‘lmaydi.")

    def delete(self):
        raise TypeError("Ombor harakatlari jurnalini o‘chirib bo‘lmaydi.")


class InventoryEntry(CompanyOwnedModel):
    class Type(models.TextChoices):
        RECEIPT = "receipt", "Kirim"
        ISSUE = "issue", "Chiqim"
        ADJUSTMENT = "adjustment", "Tuzatish"
        RESERVATION = "reservation", "Zaxira"
        RELEASE = "release", "Zaxira qaytarildi"
        DELIVERY = "delivery", "Yetkazildi"
        REVERSAL = "reversal", "Teskari yozuv"

    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="inventory_entries"
    )
    entry_type = models.CharField(max_length=16, choices=Type.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reserved_delta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    batch_number = models.CharField(max_length=120, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_entries",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_entries",
    )
    trip = models.ForeignKey(
        "logistics.Trip",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_entries",
    )
    idempotency_key = models.CharField(max_length=160, blank=True)
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
    )

    objects = InventoryEntryQuerySet.as_manager()

    class Meta:
        ordering = ("-occurred_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0, reserved_delta=0),
                name="inventory_entry_nonzero",
            ),
            models.UniqueConstraint(
                fields=("company", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="uniq_inventory_idempotency_company",
            ),
        ]
        indexes = [
            models.Index(fields=("company", "product", "-occurred_at")),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and self.product.company_id != self.company_id:
            errors["product"] = "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."
        if self.order_id and self.order.company_id != self.company_id:
            errors["order"] = "Buyurtma shu kompaniyaga tegishli bo‘lishi kerak."
        if self.order_item_id and (
            self.order_item.company_id != self.company_id
            or self.order_item.product_id != self.product_id
            or (self.order_id and self.order_item.order_id != self.order_id)
        ):
            errors["order_item"] = "Buyurtma bandi shu kompaniya va mahsulotga mos bo‘lishi kerak."
        if self.trip_id and self.trip.company_id != self.company_id:
            errors["trip"] = "Reys shu kompaniyaga tegishli bo‘lishi kerak."
        if self.reversal_of_id and (
            self.reversal_of.company_id != self.company_id
            or self.reversal_of.product_id != self.product_id
        ):
            errors["reversal_of"] = "Teskari yozuv shu kompaniya va mahsulotga tegishli bo‘lishi kerak."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise TypeError("Ombor harakatlari jurnalini tahrirlab bo‘lmaydi.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Ombor harakatlari jurnalini o‘chirib bo‘lmaydi.")
