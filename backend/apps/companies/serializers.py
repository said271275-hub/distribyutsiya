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


class DirectoryCompanySerializer(serializers.ModelSerializer):
    subscription_status = serializers.SerializerMethodField()
    subscription_id = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "slug",
            "logo",
            "description",
            "service_districts",
            "contact_phone",
            "brand_color",
            "order_cutoff_time",
            "subscription_status",
            "subscription_id",
        )

    def get_subscription_status(self, company) -> str:
        shop = self.context.get("shop")
        if not shop:
            return "none"
        links_map = self.context.get("links_map")
        if links_map is not None:
            link = links_map.get(company.id)
        else:
            link = company.company_links.filter(shop=shop).first()
        return link.status if link else "none"

    def get_subscription_id(self, company) -> int | None:
        shop = self.context.get("shop")
        if not shop:
            return None
        links_map = self.context.get("links_map")
        if links_map is not None:
            link = links_map.get(company.id)
        else:
            link = company.company_links.filter(shop=shop).first()
        return link.id if link else None


class MyCompanySubscriptionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_logo = serializers.ImageField(source="company.logo", read_only=True)
    company_phone = serializers.CharField(source="company.contact_phone", read_only=True)
    company_order_cutoff_time = serializers.TimeField(source="company.order_cutoff_time", read_only=True)

    class Meta:
        from apps.companies.models import CompanyShopLink
        model = CompanyShopLink
        fields = (
            "id",
            "company_id",
            "company_name",
            "company_logo",
            "company_phone",
            "company_order_cutoff_time",
            "status",
            "is_active",
            "requested_at",
            "decided_at",
            "reject_reason",
        )


class CompanySubscriptionRequestSerializer(serializers.ModelSerializer):
    shop_id = serializers.IntegerField(source="shop.id", read_only=True)
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    district = serializers.CharField(source="shop.district", read_only=True)
    phone_primary = serializers.SerializerMethodField()
    phone_secondary = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        from apps.companies.models import CompanyShopLink
        model = CompanyShopLink
        fields = (
            "id",
            "shop_id",
            "shop_name",
            "district",
            "status",
            "is_active",
            "requested_at",
            "decided_at",
            "reject_reason",
            "phone_primary",
            "phone_secondary",
            "address",
            "owner_name",
        )

    def get_phone_primary(self, obj) -> str | None:
        return obj.shop.phone_primary if obj.status == "active" else None

    def get_phone_secondary(self, obj) -> str | None:
        return obj.shop.phone_secondary if obj.status == "active" else None

    def get_address(self, obj) -> str | None:
        return obj.shop.address if obj.status == "active" else None

    def get_owner_name(self, obj) -> str | None:
        return obj.shop.owner_name if obj.status == "active" else None


class SubscriptionRejectInputSerializer(serializers.Serializer):
    reject_reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")



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


class DirectoryCompanySerializer(serializers.ModelSerializer):
    subscription_status = serializers.SerializerMethodField()
    subscription_id = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "slug",
            "logo",
            "description",
            "service_districts",
            "contact_phone",
            "brand_color",
            "order_cutoff_time",
            "subscription_status",
            "subscription_id",
        )

    def get_subscription_status(self, company) -> str:
        shop = self.context.get("shop")
        if not shop:
            return "none"
        links_map = self.context.get("links_map")
        if links_map is not None:
            link = links_map.get(company.id)
        else:
            link = company.company_links.filter(shop=shop).first()
        return link.status if link else "none"

    def get_subscription_id(self, company) -> int | None:
        shop = self.context.get("shop")
        if not shop:
            return None
        links_map = self.context.get("links_map")
        if links_map is not None:
            link = links_map.get(company.id)
        else:
            link = company.company_links.filter(shop=shop).first()
        return link.id if link else None


class MyCompanySubscriptionSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_logo = serializers.ImageField(source="company.logo", read_only=True)
    company_phone = serializers.CharField(source="company.contact_phone", read_only=True)
    company_order_cutoff_time = serializers.TimeField(source="company.order_cutoff_time", read_only=True)

    class Meta:
        from apps.companies.models import CompanyShopLink
        model = CompanyShopLink
        fields = (
            "id",
            "company_id",
            "company_name",
            "company_logo",
            "company_phone",
            "company_order_cutoff_time",
            "status",
            "is_active",
            "requested_at",
            "decided_at",
            "reject_reason",
        )


class CompanySubscriptionRequestSerializer(serializers.ModelSerializer):
    shop_id = serializers.IntegerField(source="shop.id", read_only=True)
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    district = serializers.CharField(source="shop.district", read_only=True)
    phone_primary = serializers.SerializerMethodField()
    phone_secondary = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        from apps.companies.models import CompanyShopLink
        model = CompanyShopLink
        fields = (
            "id",
            "shop_id",
            "shop_name",
            "district",
            "status",
            "is_active",
            "requested_at",
            "decided_at",
            "reject_reason",
            "phone_primary",
            "phone_secondary",
            "address",
            "owner_name",
        )

    def get_phone_primary(self, obj) -> str | None:
        return obj.shop.phone_primary if obj.status == "active" else None

    def get_phone_secondary(self, obj) -> str | None:
        return obj.shop.phone_secondary if obj.status == "active" else None

    def get_address(self, obj) -> str | None:
        return obj.shop.address if obj.status == "active" else None

    def get_owner_name(self, obj) -> str | None:
        return obj.shop.owner_name if obj.status == "active" else None


class SubscriptionRejectInputSerializer(serializers.Serializer):
    reject_reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


