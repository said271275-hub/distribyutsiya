from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from apps.core.models import CompanyOwnedModel
from apps.companies.models import CompanyShopLink


class Payment(CompanyOwnedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Naqd"
        CARD = "card", "Karta"
        BANK_TRANSFER = "bank_transfer", "Bank o‘tkazmasi"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        CONFIRMED = "confirmed", "Tasdiqlandi"
        CANCELLED = "cancelled", "Bekor qilindi"

    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=(MinValueValidator(0.01),)
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.shop_id and not CompanyShopLink.objects.filter(
            company_id=self.company_id, shop_id=self.shop_id, is_active=True
        ).exists():
            raise ValidationError({"shop": "Do‘kon faol kompaniya bilan bog‘lanmagan."})


class ShopBalance(CompanyOwnedModel):
    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="balances"
    )
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "shop"), name="uniq_shop_balance_company"
            )
        ]


class BalanceEntry(CompanyOwnedModel):
    class Direction(models.TextChoices):
        DEBIT = "debit", "Qarzga qo‘shildi"
        CREDIT = "credit", "Qarzdan ayirildi"

    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="balance_entries"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=(MinValueValidator(0.01),)
    )
    direction = models.CharField(max_length=6, choices=Direction.choices)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, null=True, blank=True,
        related_name="balance_entries",
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, null=True, blank=True,
        related_name="balance_entries",
    )
    note = models.TextField(blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="balance_entry_amount_positive")
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id and (
            self.order.company_id != self.company_id or self.order.shop_id != self.shop_id
        ):
            errors["order"] = "Buyurtma shu kompaniya va do‘konga tegishli bo‘lishi kerak."
        if self.payment_id and (
            self.payment.company_id != self.company_id or self.payment.shop_id != self.shop_id
        ):
            errors["payment"] = "To‘lov shu kompaniya va do‘konga tegishli bo‘lishi kerak."
        if errors:
            raise ValidationError(errors)

    def post(self):
        if not self.pk:
            raise ValueError("Saqlanmagan balans yozuvini o‘tkazib bo‘lmaydi.")
        with transaction.atomic():
            entry = BalanceEntry.objects.select_for_update().get(pk=self.pk)
            if entry.posted_at:
                self.posted_at = entry.posted_at
                return
            balance, _ = ShopBalance.objects.get_or_create(
                company_id=entry.company_id, shop_id=entry.shop_id
            )
            amount = entry.amount
            if entry.direction == self.Direction.CREDIT:
                amount = -amount
            ShopBalance.objects.filter(pk=balance.pk).update(
                current_balance=F("current_balance") + amount,
                updated_at=timezone.now(),
            )
            entry.posted_at = timezone.now()
            entry.save(update_fields=("posted_at", "updated_at"))
            self.posted_at = entry.posted_at
