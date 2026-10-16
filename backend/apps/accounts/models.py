from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class LoginAttempt(models.Model):
    phone = models.CharField(max_length=20)
    ip_address = models.GenericIPAddressField()
    scope = models.CharField(max_length=12)
    failures = models.PositiveSmallIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("phone", "ip_address", "scope"),
                name="uniq_login_attempt_phone_ip_scope",
            )
        ]


class PhoneOTP(models.Model):
    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Ro‘yxatdan o‘tish"

    phone = models.CharField(max_length=20)
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("phone", "purpose", "created_at"))]


class PhoneOTPSendWindow(models.Model):
    phone = models.CharField(max_length=20, unique=True)
    window_started_at = models.DateTimeField(default=timezone.now)
    sent_count = models.PositiveSmallIntegerField(default=0)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Telefon raqami majburiy.")
        user = self.model(phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser is_staff=True bo‘lishi kerak.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser is_superuser=True bo‘lishi kerak.")
        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super administrator"
        COMPANY_ADMIN = "company_admin", "Kompaniya administratori"
        DRIVER = "driver", "Haydovchi"
        SHOP_OWNER = "shop_owner", "Do‘kon egasi"

    phone = models.CharField(max_length=20, unique=True)
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    auth_version = models.PositiveIntegerField(default=0)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ("phone",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        role__in=("company_admin", "driver"),
                        company__isnull=False,
                    )
                    | models.Q(
                        role__in=("super_admin", "shop_owner"),
                        company__isnull=True,
                    )
                ),
                name="user_company_role_consistency",
            )
        ]

    def clean(self):
        super().clean()
        if self.role in {self.Role.COMPANY_ADMIN, self.Role.DRIVER} and not self.company_id:
            raise ValidationError({"company": "Bu rol uchun kompaniya majburiy."})
        if self.role in {self.Role.SUPER_ADMIN, self.Role.SHOP_OWNER} and self.company_id:
            raise ValidationError({"company": "Bu rol kompaniyasiz bo‘lishi kerak."})

    def __str__(self):
        return self.phone


class DeletionRequest(models.Model):
    class Reason(models.TextChoices):
        STORE_CLOSED = "store_closed", "Do‘kon yopildi"
        MOVED = "moved", "Ko‘chib ketdim"
        NOT_NEEDED = "not_needed", "Endi kerak emas"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        APPROVED = "approved", "Tasdiqlandi"
        CANCELLED = "cancelled", "Bekor qilindi"
        COMPLETED = "completed", "Bajarildi"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="deletion_requests")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    reason_other = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    scheduled_for = models.DateTimeField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def save(self, *args, **kwargs):
        if not self.scheduled_for:
            self.scheduled_for = self.requested_at + timedelta(days=30)
        super().save(*args, **kwargs)
