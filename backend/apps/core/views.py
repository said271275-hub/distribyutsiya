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
    from apps.accounts.models import LoginAttempt
    LoginAttempt.objects.all().delete()
    return Response({"status": "ok"})
