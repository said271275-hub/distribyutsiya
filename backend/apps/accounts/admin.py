from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import DeletionRequest, User
from apps.audit.models import AuditLog


admin.site.site_header = _("Tarqatuv boshqaruv tizimi")
admin.site.site_title = _("Tarqatuv | Boshqaruv")
admin.site.index_title = _("Boshqaruv bo‘limlari")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    verbose_name = _("Foydalanuvchi")
    verbose_name_plural = _("Foydalanuvchilar")
    ordering = ("phone",)
    list_display = ("phone", "role", "company", "is_active", "is_blocked", "is_staff")
    list_filter = ("role", "company", "is_active", "is_blocked", "is_staff", "is_deleted")
    search_fields = ("phone", "company__name")
    list_per_page = 50
    fieldsets = (
        (_("Kirish ma’lumotlari"), {"fields": ("phone", "password")}),
        (_("Kompaniya va vazifa"), {"fields": ("company", "role")}),
        (_("Hisob holati"), {"fields": ("is_active", "is_blocked", "is_deleted")}),
        (_("Boshqaruv huquqlari"), {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Faollik va vaqt"), {"fields": ("last_login_label", "date_joined")}),
    )
    readonly_fields = ("last_login_label",)
    add_fieldsets = (
        (
            _("Yangi hisob ma’lumotlari"),
            {
                "classes": ("wide",),
                "fields": ("phone", "role", "company", "password1", "password2"),
            },
        ),
    )

    def _can_manage_accounts(self, request):
        return (
            request.user.is_authenticated
            and request.user.role == User.Role.SUPER_ADMIN
        )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        translated_labels = {
            "password": _("Parol"),
            "is_superuser": _("Barcha ruxsatlarga ega"),
            "groups": _("Guruhlar"),
            "user_permissions": _("Foydalanuvchi ruxsatlari"),
        }
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield and db_field.name in translated_labels:
            formfield.label = translated_labels[db_field.name]
        return formfield

    @admin.display(description=_("Oxirgi kirish vaqti"))
    def last_login_label(self, obj):
        return obj.last_login

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
    search_fields = ("user__phone", "user__company__name", "reason_other")
    date_hierarchy = "requested_at"
    list_per_page = 50
    readonly_fields = (
        "user", "reason", "reason_other", "requested_at", "scheduled_for", "processed_at"
    )
    fieldsets = (
        (_("So‘rov tafsilotlari"), {"fields": ("user", "reason", "reason_other")}),
        (_("Ko‘rib chiqish"), {"fields": ("status", "requested_at", "scheduled_for", "processed_at")}),
    )

    def has_add_permission(self, request):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at_label", "company", "actor", "action", "entity_type", "entity_id"
    )
    list_filter = ("company", "action", "entity_type")
    search_fields = ("entity_type", "entity_id", "actor__phone", "company__name", "action")
    date_hierarchy = "created_at"
    list_per_page = 100
    readonly_fields = (
        "company", "actor", "action", "entity_type", "entity_id",
        "before", "after", "created_at_label", "updated_at_label",
    )
    fieldsets = (
        (_("Harakat tafsilotlari"), {
            "fields": (
                "created_at_label", "updated_at_label", "company", "actor",
                "action", "entity_type", "entity_id",
            )
        }),
        (_("O‘zgarishlar"), {"fields": ("before", "after")}),
    )

    @admin.display(description=_("Yaratilgan vaqt"), ordering="created_at")
    def created_at_label(self, obj):
        return obj.created_at

    @admin.display(description=_("Yangilangan vaqt"), ordering="updated_at")
    def updated_at_label(self, obj):
        return obj.updated_at

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
