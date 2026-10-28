from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_field

from apps.accounts.models import User
from apps.accounts.services import normalize_uz_phone
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.core.permissions import ShopOwnerPermission


class ShopProfileSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(read_only=True)
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)
    company_contacts = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = (
            "id", "owner_id", "owner_phone", "name", "owner_name",
            "phone_primary", "phone_secondary", "address", "district",
            "latitude", "longitude", "company_contacts", "sms_notifications_enabled",
        )

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_company_contacts(self, shop):
        links = CompanyShopLink.objects.filter(
            shop=shop, is_active=True, company__is_active=True
        ).select_related("company")
        return [
            {
                "id": link.company_id,
                "name": link.company.name,
                "phone": link.company.contact_phone,
            }
            for link in links
        ]

    def validate_phone_primary(self, value):
        return normalize_uz_phone(value)

    def validate_phone_secondary(self, value):
        return normalize_uz_phone(value) if value else ""


class ShopProfileCreateSerializer(ShopProfileSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.filter(is_active=True), write_only=True
    )

    class Meta(ShopProfileSerializer.Meta):
        fields = ShopProfileSerializer.Meta.fields + ("company_id",)


class ShopCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "contact_phone", "order_cutoff_time")


class ShopCompanyListView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)

    @extend_schema(responses=ShopCompanySerializer(many=True))
    def get(self, request):
        companies = Company.objects.filter(is_active=True)
        return Response(ShopCompanySerializer(companies, many=True).data)


class ShopProfileView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)

    def get_shop(self, user):
        return get_object_or_404(Shop.objects.filter(owner=user))

    @extend_schema(responses=ShopProfileSerializer)
    def get(self, request):
        shop = self.get_shop(request.user)
        return Response(ShopProfileSerializer(shop).data)

    @extend_schema(request=ShopProfileCreateSerializer, responses={201: ShopProfileSerializer})
    def post(self, request):
        if request.user.shops.exists():
            return Response({"detail": "Do‘kon profili allaqachon yaratilgan."}, status=400)
        serializer = ShopProfileCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        company = data.pop("company")
        with transaction.atomic():
            owner = User.objects.select_for_update().get(pk=request.user.pk)
            if owner.shops.exists():
                return Response({"detail": "Do‘kon profili allaqachon yaratilgan."}, status=400)
            company = Company.objects.select_for_update().filter(
                pk=company.pk, is_active=True
            ).first()
            if company is None:
                return Response({"detail": "Kompaniya faol emas."}, status=400)
            shop = Shop.objects.create(owner=owner, **data)
            CompanyShopLink.objects.create(company=company, shop=shop)
        return Response(ShopProfileSerializer(shop).data, status=201)

    @extend_schema(request=ShopProfileSerializer, responses=ShopProfileSerializer)
    def patch(self, request):
        shop = self.get_shop(request.user)
        serializer = ShopProfileSerializer(shop, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)