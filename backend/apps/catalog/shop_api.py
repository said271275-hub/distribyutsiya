from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.companies.models import CompanyShopLink, Shop, ShopPrice
from apps.core.permissions import ShopOwnerPermission


class ShopCatalogPagination(PageNumberPagination):
    page_size = 24


class ShopCatalogProductSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    company_phone = serializers.CharField(source="company.contact_phone", read_only=True)
    company_cutoff_time = serializers.TimeField(source="company.order_cutoff_time", read_only=True)
    image_url = serializers.SerializerMethodField()
    base_price = serializers.DecimalField(source="price", max_digits=12, decimal_places=2)
    unit_price = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "company_id", "company_name", "company_phone", "company_cutoff_time", "name",
            "image_url", "unit", "base_price", "unit_price", "discount_percent",
        )

    def _shop_price(self, product):
        rows = getattr(product, "shop_specific_prices", ())
        return rows[0] if rows else None

    @extend_schema_field(OpenApiTypes.URI)
    def get_image_url(self, product):
        if not product.image:
            return None
        request = self.context.get("request")
        url = product.image.url
        return request.build_absolute_uri(url) if request else url

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_discount_percent(self, product):
        shop_price = self._shop_price(product)
        discount = shop_price.discount_percent if shop_price else Decimal("0.00")
        return format(discount, ".2f")

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_unit_price(self, product):
        shop_price = self._shop_price(product)
        base_price = shop_price.price if shop_price and shop_price.price is not None else product.price
        discount = shop_price.discount_percent if shop_price else Decimal("0")
        price = (base_price * (Decimal("100") - discount) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return format(price, ".2f")


class ShopCatalogView(generics.ListAPIView):
    serializer_class = ShopCatalogProductSerializer
    permission_classes = (IsAuthenticated, ShopOwnerPermission)
    pagination_class = ShopCatalogPagination
    filter_backends = ()

    def get_queryset(self):
        shop = get_object_or_404(Shop, owner=self.request.user)
        links = CompanyShopLink.objects.filter(
            shop=shop, is_active=True, company__is_active=True
        )
        company_ids = links.values_list("company_id", flat=True)
        company_filter = self.request.query_params.get("company")
        if company_filter:
            try:
                company_id = int(company_filter)
            except ValueError as error:
                raise ValidationError({"company": "Kompaniya ID raqami noto‘g‘ri."}) from error
            company_ids = company_ids.filter(company_id=company_id)

        search = self.request.query_params.get("search", "").strip()

        shop_prices = ShopPrice.objects.filter(shop=shop)
        return (
            Product.objects.filter(
                company_id__in=company_ids, is_active=True, is_archived=False
            )
            .select_related("company")
            .prefetch_related(
                Prefetch("shop_prices", queryset=shop_prices, to_attr="shop_specific_prices")
            )
            .filter(Q(name__icontains=search) if search else Q())
        )