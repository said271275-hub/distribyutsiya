from decimal import Decimal
from django.utils import timezone

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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
    delivered_quantity = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=(MinValueValidator(Decimal("0.00")),),
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


class RecurringOrderSchedule(CompanyOwnedModel):
    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="recurring_order_schedules"
    )
    name = models.CharField(max_length=120)
    weekdays = models.JSONField(default=list)
    delivery_time_from = models.TimeField(null=True, blank=True)
    delivery_time_to = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ("name", "pk")
        indexes = [models.Index(fields=("shop", "is_active", "is_archived"))]

    def clean(self):
        super().clean()
        errors = {}
        if self.shop_id and not CompanyShopLink.objects.filter(
            company_id=self.company_id,
            shop_id=self.shop_id,
            is_active=True,
            company__is_active=True,
        ).exists():
            errors["shop"] = "Do‘kon faol kompaniya bilan bog‘lanmagan."
        if not isinstance(self.weekdays, list) or not self.weekdays:
            errors["weekdays"] = "Kamida bitta yetkazish kunini tanlang."
        elif any(type(day) is not int or day < 0 or day > 6 for day in self.weekdays):
            errors["weekdays"] = "Hafta kunlari noto‘g‘ri."
        elif len(self.weekdays) != len(set(self.weekdays)):
            errors["weekdays"] = "Hafta kunini takrorlamang."
        if (
            self.delivery_time_from
            and self.delivery_time_to
            and self.delivery_time_from >= self.delivery_time_to
        ):
            errors["delivery_time_to"] = "Yetkazish oralig‘i boshlanishdan keyin tugashi kerak."
        if errors:
            raise ValidationError(errors)


class RecurringOrderScheduleItem(CompanyOwnedModel):
    schedule = models.ForeignKey(
        RecurringOrderSchedule, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="recurring_schedule_items"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=(
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("10000.00")),
        ),
    )

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("schedule", "product"), name="uniq_recurring_schedule_product"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0, quantity__lte=10000),
                name="recurring_schedule_item_quantity_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.schedule_id and self.company_id != self.schedule.company_id:
            raise ValidationError({"schedule": "Jadval shu kompaniyaga tegishli bo‘lishi kerak."})
        if self.product_id and self.company_id != self.product.company_id:
            raise ValidationError({"product": "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."})


class RecurringOrderDraft(CompanyOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Tasdiq kutilmoqda"
        CONFIRMED = "confirmed", "Tasdiqlandi"
        CANCELLED = "cancelled", "Bekor qilindi"
        EXPIRED = "expired", "Muddati o‘tdi"

    schedule = models.ForeignKey(
        RecurringOrderSchedule, on_delete=models.PROTECT, related_name="drafts"
    )
    delivery_date = models.DateField()
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    skipped_products = models.JSONField(default=list)
    order = models.OneToOneField(
        Order, on_delete=models.PROTECT, null=True, blank=True, related_name="recurring_draft"
    )

    class Meta:
        ordering = ("delivery_date", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("schedule", "delivery_date"), name="uniq_recurring_schedule_delivery"
            )
        ]
        indexes = [models.Index(fields=("company", "status", "delivery_date"))]

    def clean(self):
        super().clean()
        if self.schedule_id and (
            self.company_id != self.schedule.company_id
            or self.shop_id != self.schedule.shop_id
        ):
            raise ValidationError({"schedule": "Qoralama shu jadval va do‘konga tegishli bo‘lishi kerak."})


class RecurringOrderDraftItem(CompanyOwnedModel):
    draft = models.ForeignKey(
        RecurringOrderDraft, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="recurring_draft_items"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=(
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("10000.00")),
        ),
    )

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("draft", "product"), name="uniq_recurring_draft_product"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0, quantity__lte=10000),
                name="recurring_draft_item_quantity_range",
            ),
        ]

    def clean(self):
        super().clean()
        if self.draft_id and self.company_id != self.draft.company_id:
            raise ValidationError({"draft": "Qoralama shu kompaniyaga tegishli bo‘lishi kerak."})
        if self.product_id and self.company_id != self.product.company_id:
            raise ValidationError({"product": "Mahsulot shu kompaniyaga tegishli bo‘lishi kerak."})


class SmsOutbox(models.Model):
    class Event(models.TextChoices):
        RECEIVED = "received", "Qabul qilindi"
        CONFIRMED = "confirmed", "Tasdiqlandi"
        TRIP_ASSIGNED = "trip_assigned", "Reysga qo‘shildi"
        DELIVERED = "delivered", "Yetkazildi"
        SHOP_CLOSED = "shop_closed", "Do‘kon yopiq"
        PARTIAL_DELIVERY = "partial_delivery", "Qisman yetkazildi"
        RECURRING_DRAFT = "recurring_draft", "Takroriy buyurtma qoralamasi"

    class State(models.TextChoices):
        PENDING = "pending", "Navbatda"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"
        SUPPRESSED = "suppressed", "O‘chirib qo‘yilgan"

    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, null=True, blank=True, related_name="sms_outbox"
    )
    recurring_draft = models.ForeignKey(
        RecurringOrderDraft,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sms_outbox",
    )
    event = models.CharField(max_length=20, choices=Event.choices)
    eta = models.DateTimeField(null=True, blank=True)
    state = models.CharField(
        max_length=12, choices=State.choices, default=State.PENDING
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("state", "next_attempt_at"))]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(order__isnull=False, recurring_draft__isnull=True)
                    | models.Q(order__isnull=True, recurring_draft__isnull=False)
                ),
                name="sms_outbox_one_target",
            )
        ]
