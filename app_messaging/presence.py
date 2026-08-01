"""Présence en ligne — statut User.online_status + diffusion WS."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()

_CACHE_TTL = 60 * 60 * 24


def _conn_key(user_id: int) -> str:
    return f"presence:conn:{user_id}"


def visible_online_for(user) -> bool:
    """Respecte le réglage show_online_status."""
    if not getattr(user, "online_status", False):
        return False
    settings = getattr(user, "settings", None)
    if settings is not None and hasattr(settings, "show_online_status"):
        return bool(settings.show_online_status)
    try:
        from authentication.models import UserSettings

        us = UserSettings.objects.filter(user_id=user.id).only("show_online_status").first()
        if us is not None:
            return bool(us.show_online_status)
    except Exception:
        pass
    return True


def presence_connect(user_id: int) -> None:
    key = _conn_key(user_id)
    n = int(cache.get(key) or 0) + 1
    cache.set(key, n, timeout=_CACHE_TTL)
    if n == 1:
        User.objects.filter(pk=user_id).update(online_status=True)
        broadcast_presence(user_id, True)


def presence_disconnect(user_id: int) -> None:
    key = _conn_key(user_id)
    n = max(0, int(cache.get(key) or 1) - 1)
    cache.set(key, n, timeout=_CACHE_TTL)
    if n == 0:
        User.objects.filter(pk=user_id).update(online_status=False)
        broadcast_presence(user_id, False)


def broadcast_presence(user_id: int, online: bool) -> None:
    """Préviens les partenaires de conversation (inbox + chats ouverts)."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return
    # Si l'utilisateur masque son statut, toujours diffuser offline côté UI
    effective_online = online and visible_online_for(user)

    partner_ids = (
        User.objects.filter(conversations__participants=user_id)
        .exclude(id=user_id)
        .distinct()
        .values_list("id", flat=True)
    )
    for pid in partner_ids:
        async_to_sync(channel_layer.group_send)(
            f"user_messages_{pid}",
            {
                "type": "presence_update_event",
                "user_id": user_id,
                "online": effective_online,
            },
        )

    # Chats ouverts avec cet utilisateur
    from .models import Conversation

    conv_ids = Conversation.objects.filter(participants=user_id).values_list("id", flat=True)
    for cid in conv_ids:
        async_to_sync(channel_layer.group_send)(
            f"chat_{cid}",
            {
                "type": "presence_update_event",
                "user_id": user_id,
                "online": effective_online,
            },
        )


def mark_delivered_if_recipient_online(message) -> bool:
    """Passe sent → received si un destinataire est en ligne. Retourne True si mis à jour."""
    if message.status != "sent":
        return False
    online_recipient = (
        message.conversation.participants.filter(online_status=True)
        .exclude(id=message.sender_id)
        .exists()
    )
    if not online_recipient:
        return False
    message.status = "received"
    message.save(update_fields=["status"])
    return True


def absolute_media_url(file_field, request=None) -> str | None:
    """URL média joignable depuis le mobile (évite localhost du Host header)."""
    if not file_field:
        return None
    try:
        url = file_field.url
    except (ValueError, AttributeError):
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    from django.conf import settings

    base = (getattr(settings, "PUBLIC_API_BASE_URL", None) or "").rstrip("/")
    if not base and request is not None:
        return request.build_absolute_uri(url)
    if not base:
        return url
    if not url.startswith("/"):
        url = f"/{url}"
    return f"{base}{url}"
