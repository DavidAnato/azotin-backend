from django.apps import AppConfig


class AppNotificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app_notification"

    def ready(self):
        from . import signals  # noqa: F401
