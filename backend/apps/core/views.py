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
