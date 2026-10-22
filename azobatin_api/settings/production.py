from decouple import config

from .base import *  # noqa: F403, F401

# Production settings
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = [config("ALLOWED_HOSTS", default="azobatin.api.latoure.net")]
CSRF_TRUSTED_ORIGINS = [
    config("CSRF_TRUSTED_ORIGINS", default="https://azobatin.api.latoure.net")
]

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
