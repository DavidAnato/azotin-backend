from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import UserNotification
import json

def create_user_notification(recipient, message, object=None):
    """
    Crée une notification et l'envoie en temps réel via WebSocket
    """
    # Créer la notification dans la base de données
    notification = UserNotification.objects.create(
        recipient=recipient,
        message=message,
        object=object
    )

    # Préparer les données de la notification
    notification_data = {
        "id": notification.id,
        "message": notification.message,
        "object": notification.object,
        "created_at": notification.created_at.isoformat()
    }

    # Envoyer la notification via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{recipient.id}",
        {
            "type": "notification",
            "notification": notification_data
        }
    )

    return notification