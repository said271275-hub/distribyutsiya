from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.accounts.services import audit_event
from apps.companies.models import Company, CompanyShopLink, Shop, ShopPrice


@admin.action(description=_("Tanlangan kompaniyalarni tasdiqlash (Faol qilish)"))
def approve_companies(modeladmin, request, queryset):
    count = 0
    for company in queryset:
        company.status = Company.Status.ACTIVE
        company.is_active = True
        company.rejection_reason = ""
        company.save(update_fields=("status", "is_active", "rejection_reason", "updated_at"))
        audit_event("company_approved", user=request.user, company=company, entity_type="Company", entity_id=str(company.pk))
        count += 1
    if modeladmin:
        modeladmin.message_user(request, f"{count} ta kompaniya tasdiqlandi.")


@admin.action(description=_("Tanlangan kompaniyalarni rad etish"))
def reject_companies(modeladmin, request, queryset):
    count = 0
    for company in queryset:
        company.status = Company.Status.REJECTED
        company.is_active = False
        if not company.rejection_reason:
            company.rejection_reason = "Arizangiz ma’muriyat tomonidan rad etildi."
        company.save(update_fields=("status", "is_active", "rejection_reason", "updated_at"))
        audit_event("company_rejected", user=request.user, company=company, entity_type="Company", entity_id=str(company.pk))
        count += 1
    if modeladmin:
        modeladmin.message_user(request, f"{count} ta kompaniya rad etildi.")


@admin.action(description=_("Tanlangan kompaniyalarni to‘xtatish (Vaqtincha to‘xtatish)"))
def suspend_companies(modeladmin, request, queryset):
    count = 0
    for company in queryset:
        company.status = Company.Status.SUSPENDED
        company.is_active = False
        if not company.rejection_reason:
            company.rejection_reason = "Kompaniya faoliyati vaqtincha to‘xtatildi."
        company.save(update_fields=("status", "is_active", "rejection_reason", "updated_at"))
        audit_event("company_suspended", user=request.user, company=company, entity_type="Company", entity_id=str(company.pk))
        count += 1
    if modeladmin:
        modeladmin.message_user(request, f"{count} ta kompaniya faoliyati to‘xtatildi.")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "slug", "contact_phone", "is_active", "created_at")
    list_filter = ("status", "is_active")
    search_fields = ("name", "slug", "contact_phone", "tax_id")
    actions = [approve_companies, reject_companies, suspend_companies]
    readonly_fields = ("slug", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "status", "rejection_reason", "is_active")}),
        (_("Tafsilotlar"), {"fields": ("description", "service_districts", "tax_id", "auto_approve_subscriptions")}),
        (_("Brend va Aloqa"), {"fields": ("logo", "brand_color", "contact_phone")}),
        (_("Yetkazish sozlamalari"), {"fields": ("order_cutoff_time", "stop_duration_minutes", "average_route_speed_kph")}),
        (_("Vaqtlar"), {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "phone_primary", "district", "status")
    search_fields = ("name", "phone_primary", "owner__phone")
    list_filter = ("status", "district")


@admin.register(CompanyShopLink)
class CompanyShopLinkAdmin(admin.ModelAdmin):
    list_display = ("company", "shop", "is_active", "created_at")
    list_filter = ("is_active", "company")


@admin.register(ShopPrice)
class ShopPriceAdmin(admin.ModelAdmin):
    list_display = ("company", "shop", "product", "price", "discount_percent")
    list_filter = ("company",)

