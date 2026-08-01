"""Diffusion WebSocket des messages (chat room + inbox)."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from .models import Message


def serialize_message_payload(message: Message, local_id=None):
    from .presence import absolute_media_url

    media_data = []
    for media in message.medias.all():
        name = media.file.name.split("/")[-1] if media.file else ""
        media_data.append(
            {
                "id": media.id,
                "file": absolute_media_url(media.file),
                "message": message.id,
                "name": name,
                "type": _guess_mime(name),
            }
        )

    job_offer = None
    if message.job_offer_id:
        try:
            from app_job.serializers import JobOfferSerializer

            job_offer = dict(JobOfferSerializer(message.job_offer).data)
        except Exception:
            job_offer = None

    reply_to_summary = None
    if message.reply_to_id:
        parent = message.reply_to
        sender = parent.sender
        sender_name = (
            f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            or getattr(sender, "username", "")
            or str(sender.id)
        )
        reply_to_summary = {
            "id": parent.id,
            "content": None if parent.deleted_for_everyone else parent.content,
            "sender": {"id": sender.id, "name": sender_name},
            "has_media": parent.medias.exists() and not parent.deleted_for_everyone,
        }

    return {
        "id": message.id,
        "sender": message.sender_id,
        "sender_id": message.sender_id,
        "content": message.content,
        "medias": media_data,
        "timestamp": message.timestamp.isoformat(),
        "status": message.status,
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "read_at": message.read_at.isoformat() if message.read_at else None,
        "job_offer": job_offer,
        "local_id": local_id,
        "reply_to": reply_to_summary,
        "reply_to_id": message.reply_to_id,
    }


def _guess_mime(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")):
        return "image/jpeg" if lower.endswith((".jpg", ".jpeg")) else f"image/{lower.split('.')[-1]}"
    if lower.endswith((".mp4", ".mov", ".avi", ".webm", ".m4v")):
        return "video/mp4"
    if lower.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac")):
        return "audio/m4a"
    if lower.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


def broadcast_new_message(message: Message, local_id=None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    from .presence import mark_delivered_if_recipient_online

    if mark_delivered_if_recipient_online(message):
        message.refresh_from_db(fields=["status"])

    payload = serialize_message_payload(message, local_id=local_id)
    conversation_id = message.conversation_id
    room = f"chat_{conversation_id}"

    async_to_sync(channel_layer.group_send)(
        room, {"type": "chat_message", **payload}
    )

    if message.status == "received":
        async_to_sync(channel_layer.group_send)(
            room,
            {
                "type": "message_status_update",
                "message_ids": [message.id],
                "status": "received",
                "reader_id": None,
                "timestamp": timezone.now().isoformat(),
            },
        )

    participant_ids = list(
        message.conversation.participants.values_list("id", flat=True)
    )
    for participant_id in participant_ids:
        unread_count = (
            Message.objects.filter(
                conversation_id=conversation_id,
                status__in=["sent", "received"],
                conversation__participants=participant_id,
            )
            .exclude(sender_id=participant_id)
            .count()
        )
        async_to_sync(channel_layer.group_send)(
            f"user_messages_{participant_id}",
            {
                "type": "message_update",
                "update_type": "new_message",
                "conversation_id": conversation_id,
                "message_id": message.id,
                "sender_id": message.sender_id,
                "timestamp": payload["timestamp"],
                "status": payload["status"],
                "content": payload["content"],
                "media_urls": [m["file"] for m in payload["medias"] if m.get("file")],
                "job_offer": payload["job_offer"],
                "unread_count": unread_count,
            },
        )


def broadcast_message_status(conversation_id, message_ids, status, reader_id=None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f"chat_{conversation_id}",
        {
            "type": "message_status_update",
            "message_ids": list(message_ids),
            "status": status,
            "reader_id": reader_id,
            "timestamp": timezone.now().isoformat(),
        },
    )
