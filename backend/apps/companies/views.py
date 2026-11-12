from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import LoginAttempt, User
from apps.accounts.serializers import DetailResponseSerializer
from apps.accounts.services import audit_event, consume_registration_otp
from apps.companies.models import Company, CompanyShopLink, Shop
from apps.companies.serializers import (
    CompanyMeSerializer,
    CompanyMeUpdateSerializer,
    CompanyRegistrationSerializer,
    CompanySubscriptionRequestSerializer,
    DirectoryCompanySerializer,
    MyCompanySubscriptionSerializer,
    SubscriptionRejectInputSerializer,
)
from apps.core.permissions import CompanyAdminPermission, ShopOwnerPermission


def _check_rate_limit(ip_address: str, phone: str):
    now = timezone.now()
    phone_attempt, _ = LoginAttempt.objects.get_or_create(
        phone=phone, ip_address="0.0.0.0", scope="company_reg_phone"
    )
    ip_attempt, _ = LoginAttempt.objects.get_or_create(
        phone="__ip__", ip_address=ip_address, scope="company_reg_ip"
    )
    for attempt in (phone_attempt, ip_attempt):
        if attempt.blocked_until and attempt.blocked_until > now:
            raise ValidationError({"detail": "Juda ko‘p urinishlar bo‘ldi. Birozdan so‘ng qayta urinib ko‘ring."})


def _record_rate_limit_failure(ip_address: str, phone: str):
    now = timezone.now()
    for p, ip, sc in [
        (phone, "0.0.0.0", "company_reg_phone"),
        ("__ip__", ip_address, "company_reg_ip"),
    ]:
        att, _ = LoginAttempt.objects.get_or_create(phone=p, ip_address=ip, scope=sc)
        att.failures += 1
        if att.failures >= 5:
            att.blocked_until = now + timezone.timedelta(minutes=15)
        att.save(update_fields=("failures", "blocked_until", "updated_at"))


class CompanyRegistrationView(APIView):
    permission_classes = (AllowAny,)
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    @extend_schema(request=CompanyRegistrationSerializer, responses={201: CompanyMeSerializer})
    def post(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ip_address = request.META.get("REMOTE_ADDR", "127.0.0.1")
        phone = data["admin_phone"]
        _check_rate_limit(ip_address, phone)

        try:
            consume_registration_otp(phone, data["code"])
        except ValidationError:
            _record_rate_limit_failure(ip_address, phone)
            raise

        with transaction.atomic():
            company = Company.objects.create(
                name=data["name"],
                status=Company.Status.PENDING,
                description=data.get("description", ""),
                service_districts=data.get("service_districts", []),
                tax_id=data.get("tax_id", ""),
                contact_phone=data.get("contact_phone") or phone,
                brand_color=data.get("brand_color", ""),
                auto_approve_subscriptions=data.get("auto_approve_subscriptions", False),
            )
            admin_user = User.objects.create_user(
                phone=phone,
                password=data["password"],
                role=User.Role.COMPANY_ADMIN,
                company=company,
                is_active=True,
            )
            audit_event(
                "company_registered",
                user=admin_user,
                company=company,
                entity_type="Company",
                entity_id=str(company.pk),
            )

        return Response(
            {
                "detail": "Kompaniya muvaffaqiyatli ro‘yxatdan o‘tkazildi va tasdiqlash uchun yuborildi.",
                "company": CompanyMeSerializer(company).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CompanyMeView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_company(self, request):
        user = request.user
        if user.role == User.Role.COMPANY_ADMIN:
            if not user.company:
                raise PermissionDenied("Foydalanuvchiga kompaniya biriktirilmagan.")
            return user.company
        if user.role == User.Role.SUPER_ADMIN:
            company_id = request.query_params.get("company_id")
            if not company_id:
                raise ValidationError({"company_id": "Super admin kompaniya ID sini ko‘rsatishi kerak."})
            try:
                return Company.objects.get(pk=int(company_id))
            except (ValueError, Company.DoesNotExist):
                raise ValidationError({"company_id": "Kompaniya topilmadi."})
        raise PermissionDenied("Faqat kompaniya ma’murlari o‘z profilini ko‘rishi mumkin.")

    @extend_schema(responses={200: CompanyMeSerializer})
    def get(self, request):
        company = self.get_company(request)
        return Response(CompanyMeSerializer(company).data)

    @extend_schema(request=CompanyMeUpdateSerializer, responses={200: CompanyMeSerializer})
    def patch(self, request):
        company = self.get_company(request)
        serializer = CompanyMeUpdateSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        audit_event(
            "company_profile_updated",
            user=request.user,
            company=company,
            entity_type="Company",
            entity_id=str(company.pk),
        )
        return Response(CompanyMeSerializer(company).data)


class DirectoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class DirectoryCompanyListView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)

    def get_shop(self, user):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(Shop, owner=user)

    @extend_schema(responses={200: DirectoryCompanySerializer(many=True)})
    def get(self, request):
        shop = self.get_shop(request.user)
        queryset = Company.objects.filter(status=Company.Status.ACTIVE, is_active=True).order_by("name")

        q = request.query_params.get("q", "").strip()
        if q:
            queryset = queryset.filter(name__icontains=q)

        district = request.query_params.get("district", "").strip()
        if district:
            queryset = queryset.filter(service_districts__icontains=district)

        links = CompanyShopLink.objects.filter(shop=shop)
        links_map = {link.company_id: link for link in links}

        paginator = DirectoryPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = DirectoryCompanySerializer(
            page if page is not None else queryset,
            many=True,
            context={"shop": shop, "links_map": links_map},
        )
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)


class DirectoryCompanySubscribeView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)
    serializer_class = DetailResponseSerializer

    def get_shop(self, user):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(Shop, owner=user)

    @extend_schema(responses={200: DetailResponseSerializer})
    def post(self, request, company_id):
        from django.shortcuts import get_object_or_404
        shop = self.get_shop(request.user)
        company = get_object_or_404(Company, pk=company_id, status=Company.Status.ACTIVE, is_active=True)

        with transaction.atomic():
            link = CompanyShopLink.objects.select_for_update().filter(shop=shop, company=company).first()
            if link:
                if link.status == CompanyShopLink.Status.BLOCKED:
                    raise ValidationError({"detail": "Ushbu kompaniyaga obuna bo‘lish bloklangan."})
                if link.status == CompanyShopLink.Status.ACTIVE:
                    raise ValidationError({"detail": "Siz allaqachon ushbu kompaniyaga obuna bo‘lgansiz."})
                if link.status == CompanyShopLink.Status.PENDING:
                    raise ValidationError({"detail": "Obuna so‘rovi allaqachon yuborilgan."})

            now = timezone.now()
            auto_approve = company.auto_approve_subscriptions
            new_status = CompanyShopLink.Status.ACTIVE if auto_approve else CompanyShopLink.Status.PENDING
            is_active = auto_approve

            if link:
                link.status = new_status
                link.is_active = is_active
                link.requested_at = now
                link.decided_at = now if auto_approve else None
                link.reject_reason = ""
                link.save()
            else:
                link = CompanyShopLink.objects.create(
                    company=company,
                    shop=shop,
                    status=new_status,
                    is_active=is_active,
                    requested_at=now,
                    decided_at=now if auto_approve else None,
                )

            audit_event(
                "company_subscription_requested",
                user=request.user,
                company=company,
                entity_type="CompanyShopLink",
                entity_id=str(link.pk),
            )

        msg = "Obuna tasdiqlandi." if auto_approve else "Obuna so‘rovi yuborildi."
        return Response(
            {"detail": msg, "status": link.status, "is_active": link.is_active},
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: DetailResponseSerializer})
    def delete(self, request, company_id):
        from apps.orders.models import Order
        from apps.payments.models import ShopBalance
        from django.shortcuts import get_object_or_404

        shop = self.get_shop(request.user)
        link = get_object_or_404(CompanyShopLink, shop=shop, company_id=company_id)

        # Check for open orders
        has_open_orders = Order.objects.filter(shop=shop, company_id=company_id).exclude(
            status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
        ).exists()
        if has_open_orders:
            raise ValidationError({"detail": "Yakunlanmagan ochiq buyurtmalaringiz mavjud. Avval ularni yakunlang yoki bekor qiling."})

        # Check for debt
        balance = ShopBalance.objects.filter(shop=shop, company_id=company_id).first()
        if balance and balance.current_balance < 0:
            raise ValidationError({"detail": "Kompaniya oldida qarzdorligingiz mavjud. Avval hisob-kitobni yakunlang."})

        with transaction.atomic():
            link.status = CompanyShopLink.Status.REJECTED
            link.is_active = False
            link.decided_at = timezone.now()
            link.decided_by = request.user
            link.reject_reason = "Do‘konchi tomonidan bekor qilindi"
            link.save()

            audit_event(
                "company_subscription_cancelled",
                user=request.user,
                company=link.company,
                entity_type="CompanyShopLink",
                entity_id=str(link.pk),
            )

        return Response({"detail": "Obuna muvaffaqiyatli bekor qilindi."})


class MyShopCompaniesListView(APIView):
    permission_classes = (IsAuthenticated, ShopOwnerPermission)

    def get_shop(self, user):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(Shop, owner=user)

    @extend_schema(responses={200: MyCompanySubscriptionSerializer(many=True)})
    def get(self, request):
        shop = self.get_shop(request.user)
        links = CompanyShopLink.objects.filter(shop=shop).select_related("company").order_by("-requested_at")
        serializer = MyCompanySubscriptionSerializer(links, many=True)
        return Response(serializer.data)


class CompanySubscriptionsView(APIView):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)

    @extend_schema(responses={200: CompanySubscriptionRequestSerializer(many=True)})
    def get(self, request):
        company = request.company
        status_param = request.query_params.get("status")
        queryset = CompanyShopLink.objects.filter(company=company).select_related("shop").order_by("-requested_at")
        if status_param:
            queryset = queryset.filter(status=status_param)
        serializer = CompanySubscriptionRequestSerializer(queryset, many=True)
        return Response(serializer.data)


class CompanySubscriptionActionView(APIView):
    permission_classes = (IsAuthenticated, CompanyAdminPermission)

    @extend_schema(request=SubscriptionRejectInputSerializer, responses={200: CompanySubscriptionRequestSerializer})
    def post(self, request, pk, action):
        from django.shortcuts import get_object_or_404
        company = request.company
        link = get_object_or_404(CompanyShopLink.objects.select_related("shop"), pk=pk, company=company)

        now = timezone.now()
        with transaction.atomic():
            if action == "approve":
                link.status = CompanyShopLink.Status.ACTIVE
                link.is_active = True
                link.decided_at = now
                link.decided_by = request.user
                link.reject_reason = ""
            elif action == "reject":
                serializer = SubscriptionRejectInputSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                reason = serializer.validated_data.get("reject_reason", "").strip() or "Arizangiz rad etildi."
                link.status = CompanyShopLink.Status.REJECTED
                link.is_active = False
                link.decided_at = now
                link.decided_by = request.user
                link.reject_reason = reason
            elif action == "block":
                link.status = CompanyShopLink.Status.BLOCKED
                link.is_active = False
                link.decided_at = now
                link.decided_by = request.user
                link.reject_reason = "Do‘kon bloklandi."
            else:
                raise ValidationError({"action": "Noma’lum amal."})

            link.save()
            audit_event(
                f"company_subscription_{action}d",
                user=request.user,
                company=company,
                entity_type="CompanyShopLink",
                entity_id=str(link.pk),
            )

        return Response(CompanySubscriptionRequestSerializer(link).data)


