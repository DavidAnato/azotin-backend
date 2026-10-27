from urllib.parse import urlparse

from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403, F401

DEBUG = False


def _csv_setting(name: str) -> list[str]:
    return [item.strip() for item in config(name, default="").split(",") if item.strip()]


def _required(name: str) -> str:
    value = config(name, default="").strip()
    if not value:
        raise ImproperlyConfigured(f"La variable {name} est obligatoire en production.")
    return value


SECRET_KEY = _required("SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY in {"insecure-key", "change-me-in-production"}:
    raise ImproperlyConfigured("SECRET_KEY doit être une clé aléatoire d'au moins 50 caractères.")
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

ALLOWED_HOSTS = _csv_setting("ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS doit contenir les noms d'hôte explicites du VPS.")

CSRF_TRUSTED_ORIGINS = _csv_setting("CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = _csv_setting("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = False
for origin in CSRF_TRUSTED_ORIGINS + CORS_ALLOWED_ORIGINS:
    if urlparse(origin).scheme != "https":
        raise ImproperlyConfigured(f"L'origine de production doit utiliser HTTPS : {origin}")

if config("DEBUG", default=False, cast=bool):
    raise ImproperlyConfigured("DEBUG=True est interdit en production.")
if config("OTP_SKIP_SMS", default=False, cast=bool):
    raise ImproperlyConfigured("OTP_SKIP_SMS=True est interdit en production.")

REDIS_URL = _required("REDIS_URL")
CHANNEL_LAYERS["default"]["CONFIG"]["hosts"] = [REDIS_URL]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required("DB_NAME"),
        "USER": _required("DB_USER"),
        "PASSWORD": _required("DB_PASSWORD"),
        "HOST": _required("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "CONN_HEALTH_CHECKS": True,
    }
}

FRONTEND_URL = _required("FRONTEND_URL").rstrip("/")
PUBLIC_API_BASE_URL = _required("PUBLIC_API_BASE_URL").rstrip("/")
for name, value in (("FRONTEND_URL", FRONTEND_URL), ("PUBLIC_API_BASE_URL", PUBLIC_API_BASE_URL)):
    if urlparse(value).scheme != "https":
        raise ImproperlyConfigured(f"{name} doit utiliser HTTPS en production.")

EMAIL_HOST = _required("EMAIL_HOST")
EMAIL_HOST_USER = _required("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _required("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
if EMAIL_USE_TLS == EMAIL_USE_SSL:
    raise ImproperlyConfigured("Configurer exactement un mode SMTP : TLS ou SSL.")

FEDAPAY_ENVIRONMENT = _required("FEDAPAY_ENVIRONMENT").lower()
if FEDAPAY_ENVIRONMENT not in {"live", "sandbox"}:
    raise ImproperlyConfigured("FEDAPAY_ENVIRONMENT doit valoir 'live' ou 'sandbox'.")
if FEDAPAY_ENVIRONMENT == "live":
    _required("FEDAPAY_PUBLIC_KEY")
    _required("FEDAPAY_SECRET_KEY")
    _required("FEDAPAY_WEBHOOK_SECRET")
if config("FEDAPAY_SKIP_WEBHOOK_SIGNATURE", default=False, cast=bool):
    raise ImproperlyConfigured("La signature FedaPay ne peut pas être désactivée en production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = config("USE_X_FORWARDED_HOST", default=True, cast=bool)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31_536_000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
