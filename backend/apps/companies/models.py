from datetime import time

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import CompanyOwnedModel, TimestampedModel


class Company(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        ACTIVE = "active", "Faol"
        SUSPENDED = "suspended", "To‘xtatilgan"
        REJECTED = "rejected", "Rad etilgan"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    description = models.TextField(blank=True)
    service_districts = models.JSONField(default=list, blank=True)
    tax_id = models.CharField(max_length=30, blank=True)
    auto_approve_subscriptions = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True)
    logo = models.ImageField(upload_to="companies/logos/", blank=True)
    brand_color = models.CharField(max_length=7, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    order_cutoff_time = models.TimeField(default=time(18, 0))
    stop_duration_minutes = models.PositiveSmallIntegerField(default=15)
    average_route_speed_kph = models.PositiveSmallIntegerField(default=35)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("name"),
                name="uniq_company_name_case_insensitive",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name) or "company"
            slug = base_slug
            counter = 1
            while Company.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

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
    owner_name = models.CharField(max_length=200, blank=True)
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
    sms_notifications_enabled = models.BooleanField(default=True)

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
    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        ACTIVE = "active", "Faol"
        REJECTED = "rejected", "Rad etilgan"
        BLOCKED = "blocked", "Bloklangan"

    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="company_links")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    is_active = models.BooleanField(default=True)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_subscriptions"
    )
    reject_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)
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
