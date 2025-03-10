from django.apps import AppConfig


class AppMessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app_messaging"

    def ready(self):
        import app_messaging.signals  # noqa: F401
