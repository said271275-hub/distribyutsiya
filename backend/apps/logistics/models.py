from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import CompanyOwnedModel
from apps.companies.models import CompanyShopLink


class Vehicle(CompanyOwnedModel):
    name = models.CharField(max_length=120)
    plate_number = models.CharField(max_length=20)
    capacity = models.DecimalField(
        max_digits=12, decimal_places=2, validators=(MinValueValidator(0.01),)
    )
    volume_capacity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(0.01),),
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("company", "plate_number"), name="uniq_vehicle_plate_company"
            )
        ]


class DriverProfile(CompanyOwnedModel):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.PROTECT, related_name="driver_profile"
    )
    license_number = models.CharField(max_length=80, blank=True)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        related_name="drivers",
        null=True,
        blank=True,
    )

    def clean(self):
        super().clean()
        errors = {}
        if self.user_id and (
            self.user.role != self.user.Role.DRIVER
            or self.user.company_id != self.company_id
        ):
            errors["user"] = "Haydovchi foydalanuvchisi shu kompaniyada driver rolida bo‘lishi kerak."
        if self.vehicle_id and self.vehicle.company_id != self.company_id:
            errors["vehicle"] = "Transport haydovchi bilan bir kompaniyada bo‘lishi kerak."
        if errors:
            raise ValidationError(errors)


class Trip(CompanyOwnedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Rejalashtirilgan"
        CONFIRMED = "confirmed", "Tasdiqlangan"
        IN_PROGRESS = "in_progress", "Yo‘lda"
        COMPLETED = "completed", "Yakunlangan"
        CANCELLED = "cancelled", "Bekor qilingan"

    class RoutingSource(models.TextChoices):
        OSRM = "osrm", "OSRM"
        FALLBACK = "fallback", "Zaxira hisob"

    date = models.DateField()
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.PROTECT, related_name="trips"
    )
    driver = models.ForeignKey(
        DriverProfile, on_delete=models.PROTECT, related_name="trips"
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PLANNED
    )
    routing_source = models.CharField(
        max_length=12, choices=RoutingSource.choices,
        default=RoutingSource.FALLBACK,
    )

    def clean(self):
        super().clean()
        errors = {}
        if self.vehicle_id and self.vehicle.company_id != self.company_id:
            errors["vehicle"] = "Transport shu kompaniyaga tegishli bo‘lishi kerak."
        if self.driver_id and self.driver.company_id != self.company_id:
            errors["driver"] = "Haydovchi shu kompaniyaga tegishli bo‘lishi kerak."
        if errors:
            raise ValidationError(errors)


class TripStop(CompanyOwnedModel):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    shop = models.ForeignKey(
        "companies.Shop", on_delete=models.PROTECT, related_name="trip_stops"
    )
    sequence = models.PositiveIntegerField()
    eta = models.DateTimeField(null=True, blank=True)
    eta_window_from = models.DateTimeField(null=True, blank=True)
    eta_window_to = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    orders = models.ManyToManyField(
        "orders.Order", through="TripStopOrder", related_name="trip_stops"
    )

    class Meta:
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(
                fields=("trip", "sequence"), name="uniq_trip_stop_sequence"
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.trip_id and self.trip.company_id != self.company_id:
            errors["trip"] = "Reys shu kompaniyaga tegishli bo‘lishi kerak."
        if self.shop_id and not CompanyShopLink.objects.filter(
            company_id=self.company_id, shop_id=self.shop_id, is_active=True
        ).exists():
            errors["shop"] = "Do‘kon faol kompaniya bilan bog‘lanmagan."
        if errors:
            raise ValidationError(errors)


class TripStopOrder(CompanyOwnedModel):
    trip_stop = models.ForeignKey(
        TripStop, on_delete=models.CASCADE, related_name="order_links"
    )
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="trip_stop_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("trip_stop", "order"), name="uniq_order_per_trip_stop"
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.trip_stop_id and self.trip_stop.company_id != self.company_id:
            errors["trip_stop"] = "Reys nuqtasi shu kompaniyaga tegishli bo‘lishi kerak."
        if self.order_id and self.order.company_id != self.company_id:
            errors["order"] = "Buyurtma shu kompaniyaga tegishli bo‘lishi kerak."
        if self.trip_stop_id and self.order_id:
            if self.trip_stop.shop_id != self.order.shop_id:
                errors["order"] = "Buyurtma reys nuqtasidagi do‘konga tegishli bo‘lishi kerak."
        if errors:
            raise ValidationError(errors)


class DriverActionReceipt(models.Model):
    action_id = models.UUIDField(primary_key=True, editable=False)
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="driver_action_receipts",
    )
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="driver_action_receipts")
    stop = models.ForeignKey(TripStop, on_delete=models.CASCADE, related_name="driver_action_receipts")
    action_type = models.CharField(max_length=16)
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
