from decimal import Decimal
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.services import normalize_uz_phone, validate_user_password
from apps.companies.models import Company


MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_LOGO_FORMATS = {"JPEG", "PNG", "WEBP"}


class CompanyRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    service_districts = serializers.ListField(
        child=serializers.CharField(max_length=120, trim_whitespace=True),
        required=False,
        default=list,
    )
    tax_id = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    brand_color = serializers.CharField(max_length=7, required=False, allow_blank=True, default="")
    auto_approve_subscriptions = serializers.BooleanField(required=False, default=False)
    admin_phone = serializers.CharField(max_length=20)
    code = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(write_only=True)

    def validate_name(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Kompaniya nomini kiriting.")
        if Company.objects.filter(name__iexact=val).exists():
            raise serializers.ValidationError("Bu nomdagi kompaniya allaqachon ro‘yxatdan o‘tgan.")
        return val

    def validate_admin_phone(self, value):
        phone = normalize_uz_phone(value)
        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("Bu telefon raqami allaqachon ro‘yxatdan o‘tgan.")
        return phone

    def validate_contact_phone(self, value):
        if not value:
            return ""
        return normalize_uz_phone(value)

    def validate_password(self, value):
        validate_user_password(value)
        return value

    def validate_brand_color(self, value):
        if not value:
            return ""
        val = value.strip()
        if not val.startswith("#") or len(val) not in (4, 7):
            raise serializers.ValidationError("Brend rangi #RGB yoki #RRGGBB formatida bo‘lishi kerak.")
        return val


class CompanyMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "slug",
            "status",
            "description",
            "service_districts",
            "tax_id",
            "auto_approve_subscriptions",
            "rejection_reason",
            "logo",
            "brand_color",
            "contact_phone",
            "order_cutoff_time",
            "stop_duration_minutes",
            "average_route_speed_kph",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CompanyMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "description",
            "logo",
            "service_districts",
            "contact_phone",
            "brand_color",
            "auto_approve_subscriptions",
        )

    def validate_logo(self, value):
        if not value:
            return value
        if value.size > MAX_LOGO_SIZE_BYTES:
            raise serializers.ValidationError("Logo hajmi 2 MB dan oshmasligi kerak.")
        try:
            image = Image.open(value)
            image_format = (image.format or "").upper()
            if image_format not in ALLOWED_LOGO_FORMATS:
                raise serializers.ValidationError("Logo formati faqat JPG, PNG yoki WebP bo‘lishi mumkin.")
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise serializers.ValidationError("Yaroqsiz rasm fayli.")
        value.seek(0)
        return value

    def validate_contact_phone(self, value):
        if not value:
            return ""
        return normalize_uz_phone(value)

    def validate_brand_color(self, value):
        if not value:
            return ""
        val = value.strip()
        if not val.startswith("#") or len(val) not in (4, 7):
            raise serializers.ValidationError("Brend rangi #RGB yoki #RRGGBB formatida bo‘lishi kerak.")
        return val

