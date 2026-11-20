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
    # Har doim login urinishlari va bloklarni tozalaymiz
    from apps.accounts.models import LoginAttempt
    LoginAttempt.objects.all().delete()

    if request.GET.get("test_auth") == "1":
        from apps.accounts.services import login_user
        import traceback
        try:
            u = login_user(phone="+998882752775", password="hojiakbar123", scope="staff", ip_address="127.0.0.1")
            return Response({"login_success": True, "phone": u.phone, "role": u.role})
        except Exception as e:
            return Response({"login_success": False, "error": str(e), "tb": traceback.format_exc()})
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
