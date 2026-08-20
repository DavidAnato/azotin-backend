"""Notifications in-app + push pour le parcours escrow / portefeuille."""

from __future__ import annotations

from typing import Any

from app_notification.models import NotificationToken
from app_notification.prefs import get_notification_settings
from app_notification.utils import (
    create_user_notification,
    run_coroutine_sync,
    send_push_notification,
)


def _push_data(meta: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in meta.items():
        if value is None:
            continue
        out[key] = str(value)
    return out


def notify_user(
    user,
    message: str,
    *,
    kind: str,
    object: dict,
    push_title: str | None = None,
) -> None:
    meta = {**object, "type": kind}
    create_user_notification(recipient=user, message=message, object=meta)

    settings = get_notification_settings(user)
    if not settings.notification_push:
        return

    title = push_title or "AZOTIN"
    tokens = NotificationToken.objects.filter(user=user)
    data = _push_data(meta)
    for token in tokens:
        run_coroutine_sync(
            send_push_notification(
                token=token.token,
                title=title,
                body=message,
                data=data,
            )
        )


def contract_notif_object(contract, **extra: Any) -> dict:
    return {
        "contract_id": contract.id,
        "title": contract.title,
        **extra,
    }
