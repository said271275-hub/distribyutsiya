from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimestampedModel


class AuditLog(TimestampedModel):
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("Kompaniya"),
    )
    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("Amalni bajargan foydalanuvchi"),
    )
    action = models.CharField(_("Amal"), max_length=80)
    entity_type = models.CharField(_("Yozuv turi"), max_length=120)
    entity_id = models.CharField(_("Yozuv raqami"), max_length=64)
    before = models.JSONField(_("Oldingi qiymatlar"), null=True, blank=True)
    after = models.JSONField(_("Yangi qiymatlar"), null=True, blank=True)

    class Meta:
        verbose_name = _("Harakatlar jurnali yozuvi")
        verbose_name_plural = _("Harakatlar jurnali")
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("company", "created_at")),
            models.Index(fields=("entity_type", "entity_id")),
        ]
