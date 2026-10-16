from django.core.exceptions import FieldDoesNotExist
from rest_framework.filters import BaseFilterBackend

from apps.accounts.models import User


class CompanyTenantFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        user = request.user
        if not user or not user.is_authenticated:
            return queryset.none()
        if user.role == User.Role.SUPER_ADMIN:
            return queryset
        if user.company_id is None:
            return queryset.none()
        if queryset.model._meta.label_lower == "companies.company":
            return queryset.filter(pk=user.company_id)
        try:
            queryset.model._meta.get_field("company")
        except FieldDoesNotExist:
            return queryset.none()
        return queryset.filter(company_id=user.company_id)
