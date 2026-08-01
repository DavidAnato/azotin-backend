from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
import asyncio

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from app_notification.models import NotificationToken
from app_notification.prefs import get_notification_settings, user_wants_message_notification
from app_notification.utils import create_user_notification, send_push_notification

from .member_utils import clear_inbox_flags
from .models import ConversationMemberState, Message


def run_async(coroutine):
    """Exécute une coroutine de manière synchrone"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)


@receiver([post_save], sender=Message)
def handle_message_update(sender, instance, created, **kwargs):
    """
    Gère les mises à jour de messages (création et modification de statut)
    """
    channel_layer = get_channel_layer()

    if created:
        clear_inbox_flags(instance.conversation)

    participants = instance.conversation.participants.all()

    for participant in participants:
        has_unread = (
            Message.objects.filter(
                conversation__participants=participant, status__in=["sent", "received"]
            )
            .exclude(sender=participant)
            .exists()
        )

        try:
            async_to_sync(channel_layer.group_send)(
                f"unread_status_{participant.id}",
                {"type": "unread_status_update", "has_unread": has_unread},
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "WebSocket group_send ignoré (%s)", exc
            )

        if created and participant != instance.sender:
            muted = ConversationMemberState.objects.filter(
                conversation=instance.conversation, user=participant, muted=True
            ).exists()
            if muted:
                continue

            if not user_wants_message_notification(participant):
                continue

            preview = (
                instance.content[:100]
                if instance.content
                else "Nouveau message"
            )
            notif_message = f"Message de {instance.sender.first_name} : {preview}"
            notification = create_user_notification(
                recipient=participant,
                message=notif_message,
                object={
                    "type": "new_message",
                    "conversation_id": instance.conversation.id,
                    "sender_id": instance.sender.id,
                    "sender_name": instance.sender.first_name,
                },
            )

            settings = get_notification_settings(participant)
            if not settings.notification_push:
                continue

            tokens = NotificationToken.objects.filter(user=participant)
            push_body = preview
            for token in tokens:
                run_async(
                    send_push_notification(
                        token=token.token,
                        title=f"Message de {instance.sender.first_name}",
                        body=push_body,
                        data={
                            "type": "new_message",
                            "conversation_id": str(instance.conversation.id),
                            "sender_id": str(instance.sender.id),
                            "notification_id": notification.id,
                        },
                    )
                )


@receiver([post_delete], sender=Message)
def handle_message_delete(sender, instance, **kwargs):
    """
    Gère la suppression des messages
    """
    channel_layer = get_channel_layer()

    for participant in instance.conversation.participants.all():
        has_unread = (
            Message.objects.filter(
                conversation__participants=participant, status__in=["sent", "received"]
            )
            .exclude(sender=participant)
            .exists()
        )

        try:
            async_to_sync(channel_layer.group_send)(
                f"unread_status_{participant.id}",
                {"type": "unread_status_update", "has_unread": has_unread},
            )
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "WebSocket group_send ignoré (%s)", exc
            )
