"""Paramètres plateforme (singleton) — commission sur les contrats."""

from decimal import Decimal

from app_escrow.models import PlatformSettings


def get_platform_settings() -> PlatformSettings:
    settings_obj, _ = PlatformSettings.objects.get_or_create(
        pk=1,
        defaults={"commission_percent": Decimal("10")},
    )
    return settings_obj
