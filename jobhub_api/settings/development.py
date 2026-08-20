from decouple import config

from .base import *  # noqa: F403, F401
from .base import BASE_DIR

# Development settings

ALLOWED_HOSTS = ["*"]


# cors headers
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True


DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = ["*"]
if config("DB_ENGINE", default="sqlite3") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / config("DB_NAME", default="db.sqlite3"),
            "OPTIONS": {
                "timeout": 30,
            },
        }
    }

    # WAL + busy_timeout : réduit les "database is locked" (webhooks vs fund)
    from django.db.backends.signals import connection_created

    def _sqlite_optimize(sender, connection, **kwargs):  # noqa: ARG001
        if connection.vendor == "sqlite":
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")

    connection_created.connect(_sqlite_optimize)

# Sans identifiants SMTP : console (évite 500 en local si EMAIL_HOST n'est pas prêt)
if not config("EMAIL_HOST_USER", default="") or not config(
    "EMAIL_HOST_PASSWORD", default=""
):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Inscription : pas de SMS GetOurVoice, code OTP fixe (5 chiffres)
OTP_SKIP_SMS = config("OTP_SKIP_SMS", default=True, cast=bool)
DEV_OTP_CODE = config("DEV_OTP_CODE", default="00000")

# Redis optionnel en local : Channels in-memory pour tests / machine sans Redis.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
