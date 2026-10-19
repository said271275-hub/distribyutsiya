from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = _("Foydalanuvchilar va hisoblar")

    def ready(self):
        from importlib import import_module

        import_module("apps.accounts.signals")
        import_module("apps.accounts.openapi")
