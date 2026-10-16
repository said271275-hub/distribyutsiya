from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import DeletionRequest, User
from apps.audit.models import AuditLog


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("phone",)
    list_display = ("phone", "role", "company", "is_active", "is_blocked", "is_staff")
    list_filter = ("role", "company", "is_active", "is_blocked", "is_staff")
    search_fields = ("phone",)
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Kompaniya va rol", {"fields": ("company", "role")}),
        ("Holat", {"fields": ("is_active", "is_blocked", "is_deleted")}),
        ("Ruxsatlar", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Vaqt", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "role", "company", "password1", "password2")}),
    )

    def _can_manage_accounts(self, request):
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.SUPER_ADMIN
        )

    def has_module_permission(self, request):
        return self._can_manage_accounts(request)

    def has_view_permission(self, request, obj=None):
        return self._can_manage_accounts(request)

    def has_add_permission(self, request):
        return self._can_manage_accounts(request)

    def has_change_permission(self, request, obj=None):
        return self._can_manage_accounts(request)

    def has_delete_permission(self, request, obj=None):
        return self._can_manage_accounts(request)

    def save_model(self, request, obj, form, change):
        if not change and obj.role == User.Role.SUPER_ADMIN:
            obj.is_staff = True
        super().save_model(request, obj, form, change)


@admin.register(DeletionRequest)
class DeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "reason", "requested_at", "scheduled_for", "status")
    list_filter = ("status", "reason")
    readonly_fields = ("user", "reason", "reason_other", "requested_at", "scheduled_for")

    def has_add_permission(self, request):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "company", "actor", "action", "entity_type", "entity_id")
    list_filter = ("company", "action", "entity_type")
    readonly_fields = (
        "company", "actor", "action", "entity_type", "entity_id",
        "before", "after", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
