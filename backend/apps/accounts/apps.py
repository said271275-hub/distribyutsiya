from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from importlib import import_module

        import_module("apps.accounts.signals")
        import_module("apps.accounts.openapi")
