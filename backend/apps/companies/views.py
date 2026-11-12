from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import LoginAttempt, User
from apps.accounts.services import audit_event, consume_registration_otp
from apps.companies.models import Company
from apps.companies.serializers import (
    CompanyMeSerializer,
    CompanyMeUpdateSerializer,
    CompanyRegistrationSerializer,
)


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

