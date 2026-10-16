from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.accounts.models import User
from apps.audit.models import AuditLog


@receiver(pre_save, sender=User)
def remember_user_role(sender, instance, **kwargs):
    if instance.pk:
        instance._previous_role_company = (
            sender.objects.filter(pk=instance.pk)
            .values_list("role", "company_id")
            .first()
        )
    else:
        instance._previous_role_company = None


@receiver(post_save, sender=User)
def audit_user_role_change(sender, instance, created, **kwargs):
    previous = getattr(instance, "_previous_role_company", None)
    if previous and previous != (instance.role, instance.company_id):
        AuditLog.objects.create(
            actor=instance,
            company=instance.company,
            action="user_role_or_company_changed",
            entity_type="User",
            entity_id=str(instance.pk),
            before={"role": previous[0], "company_id": previous[1]},
            after={"role": instance.role, "company_id": instance.company_id},
        )
