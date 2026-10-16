from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import CompanyOwnedModel, TimestampedModel


class Company(TimestampedModel):
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to="companies/logos/", blank=True)
    brand_color = models.CharField(max_length=7, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Shop(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        INACTIVE = "inactive", "Nofaol"
        ARCHIVED = "archived", "Arxivlangan"

    owner = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="shops"
    )
    name = models.CharField(max_length=200)
    phone_primary = models.CharField(max_length=20, unique=True)
    phone_secondary = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=500)
    district = models.CharField(max_length=120)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=(MinValueValidator(-90), MaxValueValidator(90)),
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=(MinValueValidator(-180), MaxValueValidator(180)),
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("owner",), name="uniq_shop_owner_account"
            )
        ]

    def clean(self):
        super().clean()
        if self.owner_id and self.owner.role != self.owner.Role.SHOP_OWNER:
            raise ValidationError({"owner": "Do‘kon egasi shop_owner rolida bo‘lishi kerak."})

    def __str__(self):
        return self.name


class CompanyShopLink(CompanyOwnedModel):
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="company_links")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "shop"), name="uniq_company_shop_link"
            )
        ]


class ShopPrice(CompanyOwnedModel):
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="prices")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="shop_prices"
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=(MinValueValidator(0),),
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=(MinValueValidator(0), MaxValueValidator(100)),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "shop", "product"), name="uniq_shop_product_price"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=0, discount_percent__lte=100),
                name="shop_price_discount_range",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.product_id and self.product.company_id != self.company_id:
            errors["product"] = "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."
        if self.shop_id and not CompanyShopLink.objects.filter(
            company_id=self.company_id, shop_id=self.shop_id, is_active=True
        ).exists():
            errors["shop"] = "Do‘kon faol kompaniya bilan bog‘lanmagan."
        if errors:
            raise ValidationError(errors)
