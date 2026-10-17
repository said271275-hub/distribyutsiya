from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import CompanyOwnedModel


class Product(CompanyOwnedModel):
    class Unit(models.TextChoices):
        PIECE = "piece", "Dona"
        BOX = "box", "Quti"
        BLOCK = "block", "Blok"

    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="catalog/products/", blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=(MinValueValidator(0),)
    )
    unit_weight = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        validators=(MinValueValidator(0),),
    )
    unit_volume = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        validators=(MinValueValidator(0),),
    )
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("company", "name"), name="uniq_product_name_company")
        ]

    def __str__(self):
        return self.name


class ReturnableContainer(CompanyOwnedModel):
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=40, default="dona")
    deposit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=(MinValueValidator(0),),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("company", "name"), name="uniq_container_name_company"
            )
        ]


class ContainerMovement(CompanyOwnedModel):
    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="container_movements"
    )
    container = models.ForeignKey(
        ReturnableContainer, on_delete=models.PROTECT, related_name="movements"
    )
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=2)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, null=True, blank=True,
        related_name="container_movements",
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0), name="container_movement_nonzero"
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.container_id and self.container.company_id != self.company_id:
            errors["container"] = "Tara turi shu kompaniyaga tegishli bo‘lishi kerak."
        if self.order_id and (
            self.order.company_id != self.company_id or self.order.shop_id != self.shop_id
        ):
            errors["order"] = "Buyurtma shu kompaniya va do‘konga tegishli bo‘lishi kerak."
        if errors:
            raise ValidationError(errors)
