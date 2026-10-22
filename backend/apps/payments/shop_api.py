from decimal import Decimal

from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.companies.models import CompanyShopLink, Shop
from apps.catalog.models import ContainerMovement
from apps.core.permissions import ShopOwnerPermission
from apps.payments.models import BalanceEntry, Payment, ShopBalance


class ShopCompanyBalanceSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    company_name = serializers.CharField()
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    container_deposit = serializers.DecimalField(max_digits=18, decimal_places=4)


class ShopPaymentHistorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    company_id = serializers.IntegerField()
    company_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.CharField()
    status = serializers.CharField()
    paid_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    reference = serializers.CharField()


class ShopBalanceEntrySerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = BalanceEntry
        fields = (
            "id", "company_id", "amount", "direction", "order_id",
            "payment_id", "note", "posted_at", "created_at",
        )


class ShopFinanceSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    balances = ShopCompanyBalanceSerializer(many=True)
    payments = ShopPaymentHistorySerializer(many=True)
    entries = ShopBalanceEntrySerializer(many=True)


class ShopFinanceView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)

    @extend_schema(responses=ShopFinanceSerializer)
    def get(self, request):
        shop = get_object_or_404(Shop, owner=request.user)
        links = list(
            CompanyShopLink.objects.filter(
                shop=shop, is_active=True, company__is_active=True
            ).select_related("company")
        )
        balances = []
        total = Decimal("0.00")
        for link in links:
            balance = ShopBalance.objects.filter(
                company=link.company, shop=shop
            ).values_list("current_balance", flat=True).first() or Decimal("0.00")
            container_deposit = ContainerMovement.objects.filter(
                company=link.company, shop=shop
            ).aggregate(
                total=Sum(F("quantity_delta") * F("container__deposit_amount"))
            )["total"] or Decimal("0.00")
            total += balance
            balances.append({
                "company_id": link.company_id,
                "company_name": link.company.name,
                "balance": str(balance),
                "container_deposit": str(container_deposit),
            })
        payments = Payment.objects.filter(
            shop=shop, company_id__in=[link.company_id for link in links]
        ).select_related("company")[:50]
        entries = BalanceEntry.objects.filter(
            shop=shop, company_id__in=[link.company_id for link in links]
        )[:50]
        return Response({
            "balance": str(total),
            "balances": balances,
            "payments": [
                {
                    "id": payment.pk,
                    "company_id": payment.company_id,
                    "company_name": payment.company.name,
                    "amount": str(payment.amount),
                    "method": payment.method,
                    "status": payment.status,
                    "paid_at": payment.paid_at,
                    "created_at": payment.created_at,
                    "reference": payment.reference,
                }
                for payment in payments
            ],
            "entries": ShopBalanceEntrySerializer(entries, many=True).data,
        })