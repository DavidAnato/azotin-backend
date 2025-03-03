import asyncio

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app_notification.models import NotificationToken
from app_notification.utils import send_push_notification

from .models import Message


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

    # Déterminer les participants à notifier
    participants = instance.conversation.participants.all()

    for participant in participants:
        # Vérifier les messages non lus pour ce participant
        has_unread = (
            Message.objects.filter(
                conversation__participants=participant, status__in=["sent", "received"]
            )
            .exclude(sender=participant)
            .exists()
        )

        # Envoyer la mise à jour WebSocket
        async_to_sync(channel_layer.group_send)(
            f"unread_status_{participant.id}",
            {"type": "unread_status_update", "has_unread": has_unread},
        )

        # Si c'est un nouveau message, envoyer une notification push aux autres participants
        if created and participant != instance.sender:
            # Envoyer notification push
            tokens = NotificationToken.objects.filter(user=participant)
            for token in tokens:
                run_async(
                    send_push_notification(
                        token=token.token,
                        title=f"Message de {instance.sender.first_name}",
                        body=(
                            instance.content[:100]
                            if instance.content
                            else "Nouveau message"
                        ),
                        data={
                            "type": "new_message",
                            "conversation_id": str(instance.conversation.id),
                        },
                    )
                )


@receiver([post_delete], sender=Message)
def handle_message_delete(sender, instance, **kwargs):
    """
    Gère la suppression des messages
    """
    channel_layer = get_channel_layer()

    # Notifier tous les participants de la conversation
    for participant in instance.conversation.participants.all():
        has_unread = (
            Message.objects.filter(
                conversation__participants=participant, status__in=["sent", "received"]
            )
            .exclude(sender=participant)
            .exists()
        )

        async_to_sync(channel_layer.group_send)(
            f"unread_status_{participant.id}",
            {"type": "unread_status_update", "has_unread": has_unread},
        )
