import aiohttp
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import UserNotification


def create_user_notification(recipient, message, object=None):
    """
    Crée une notification et l'envoie en temps réel via WebSocket
    """
    # Créer la notification dans la base de données
    notification = UserNotification.objects.create(
        recipient=recipient, message=message, object=object
    )

    # Préparer les données de la notification
    notification_data = {
        "id": notification.id,
        "message": notification.message,
        "object": notification.object,
        "created_at": notification.created_at.isoformat(),
    }

    # Envoyer la notification via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{recipient.id}",
        {"type": "notification", "notification": notification_data},
    )

    return notification


async def send_push_notification(token, title, body, data=None):
    """
    Envoie une notification push à un utilisateur via Expo

    Args:
        token (str): Token Expo du destinataire
        title (str): Titre de la notification
        body (str): Corps du message
        data (dict, optional): Données supplémentaires à envoyer. Defaults to None.
    """
    if not token.startswith("ExponentPushToken["):
        print("Token invalide")
        return

    notification_data = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
    }

    if data:
        notification_data["data"] = data

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://exp.host/--/api/v2/push/send", json=[notification_data]
            ) as response:
                result = await response.json()
                return result
    except Exception as e:
        print(f"Erreur lors de l'envoi de la notification: {e}")
