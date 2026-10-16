from django.conf import settings
from django.core.exceptions import FieldDoesNotExist

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class DevelopmentOnlyPermission(BasePermission):
    def has_permission(self, _request, _view):
        return settings.DEBUG


class RolePermission(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, _view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        request.company_id = user.company_id
        request.company = user.company
        return user.role in self.allowed_roles


class CompanyAdminPermission(RolePermission):
    allowed_roles = (User.Role.SUPER_ADMIN, User.Role.COMPANY_ADMIN)


class DriverPermission(RolePermission):
    allowed_roles = (User.Role.DRIVER,)


class ShopOwnerPermission(RolePermission):
    allowed_roles = (User.Role.SHOP_OWNER,)


class CompanyScopedQuerysetMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        self.request.company_id = user.company_id
        self.request.company = user.company
        if user.role == User.Role.SUPER_ADMIN:
            return queryset
        if not user.company_id:
            return queryset.none()
        return queryset.filter(company_id=user.company_id)

    def perform_create(self, serializer):
        if self.request.user.role == User.Role.SUPER_ADMIN:
            serializer.save()
        else:
            serializer.save(company=self.request.user.company)


class ShopOwnerScopedQuerysetMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated or user.role != User.Role.SHOP_OWNER:
            return queryset.none()
        model = queryset.model
        if model._meta.label_lower == "companies.shop":
            return queryset.filter(owner_id=user.pk)
        try:
            model._meta.get_field("shop")
        except FieldDoesNotExist:
            return queryset.none()
        return queryset.filter(shop__owner_id=user.pk)


class DriverTripScopedQuerysetMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated or user.role != User.Role.DRIVER:
            return queryset.none()
        model_label = queryset.model._meta.label_lower
        if model_label == "logistics.trip":
            return queryset.filter(driver__user_id=user.pk, company_id=user.company_id)
        if model_label == "logistics.tripstop":
            return queryset.filter(trip__driver__user_id=user.pk, company_id=user.company_id)
        if model_label == "logistics.tripstoporder":
            return queryset.filter(
                trip_stop__trip__driver__user_id=user.pk,
                company_id=user.company_id,
            )
        return queryset.none()
