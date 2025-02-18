from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Message


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

        # Envoyer la mise à jour
        async_to_sync(channel_layer.group_send)(
            f"unread_status_{participant.id}",
            {"type": "unread_status_update", "has_unread": has_unread},
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
