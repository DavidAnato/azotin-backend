import logging
from typing import Dict, Optional, Tuple

import aiohttp
import httpx
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

from .models import UserNotification
from .sse import publish_notification_sse

logger = logging.getLogger(__name__)


def _notification_payload(notification: UserNotification) -> dict:
    meta = notification.object if isinstance(notification.object, dict) else {}
    kind = meta.get("type", "general")
    return {
        "id": notification.id,
        "message": notification.message,
        "object": notification.object,
        "created_at": notification.created_at.isoformat(),
        "is_read": notification.is_read,
        "kind": kind,
    }


def create_user_notification(recipient, message, object=None):
    """
    Crée une notification et la diffuse (WebSocket, SSE, statut).
    """
    notification = UserNotification.objects.create(
        recipient=recipient, message=message, object=object
    )

    notification_data = _notification_payload(notification)

    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{recipient.id}",
            {"type": "notification", "notification": notification_data},
        )
    except Exception as exc:
        logger.warning("WebSocket group_send ignoré (%s)", exc)

    publish_notification_sse(
        recipient.id,
        {"type": "user_notification", "notification": notification_data},
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


async def send_sms_async(
    phone_number: str,
    message: str,
    api_key: str,
    sender_id: Optional[str] = None,
    sender_name: Optional[str] = None,
) -> Tuple[bool, Dict]:
    if not phone_number:
        return False, {"error": "Le numéro de téléphone est requis."}
    if not message:
        return False, {"error": "Le message ne peut pas être vide."}
    if not api_key:
        return False, {"error": "La clé API Our Voice est requise."}
    if not (sender_id or sender_name):
        return False, {"error": "Vous devez fournir sender_id ou sender_name."}
    if sender_id and sender_name:
        return False, {
            "error": "Utilisez soit sender_id soit sender_name, pas les deux."
        }

    base_url = "https://api.getourvoice.com"
    endpoint = f"{base_url}/v1/messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {"to": phone_number, "body": message}
    if sender_id:
        payload["sender_id"] = sender_id
    else:
        payload["sender_name"] = sender_name

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, headers=headers, json=payload)

        if response.status_code == 401:
            return False, {"error": "Non autorisé. Vérifiez votre clé API."}
        elif response.status_code == 422:
            return False, {
                "error": "Données invalides. Vérifiez le numéro et les champs requis."
            }
        elif response.status_code == 405:
            return False, {"error": "Méthode non autorisée. Vérifiez l'URL de l'API."}

        response.raise_for_status()
        return True, response.json()

    except httpx.RequestError as e:
        return False, {"error": f"Erreur lors de l'envoi du SMS : {str(e)}"}


def send_sms_if_configured(phone_number: str, message: str) -> None:
    """Envoie un SMS seulement si OURVOICE_API_KEY est configurée (sinon noop en dev)."""
    api_key = getattr(settings, "OURVOICE_API_KEY", "") or ""
    if not api_key or not phone_number or not message:
        return
    async_to_sync(send_sms_async)(
        phone_number,
        message,
        api_key,
        sender_name="AZOTIN",
    )


def _email_can_send() -> bool:
    backend = str(getattr(settings, "EMAIL_BACKEND", ""))
    if "console" in backend or "locmem" in backend:
        return True
    user = getattr(settings, "EMAIL_HOST_USER", "") or ""
    password = getattr(settings, "EMAIL_HOST_PASSWORD", "") or ""
    return bool(user and password)


def send_email_if_configured(
    email: str, message: str, subject: str = "Notification"
) -> None:
    """N'échoue jamais la requête API (SMTP optionnel en dev)."""
    if not email or not message:
        return
    if not _email_can_send():
        return
    try:
        async_to_sync(send_email_async)(email, message, subject)
    except Exception as exc:
        logger.warning("Email non envoye vers %s: %s", email, exc)


@sync_to_async
def send_email_async(email: str, message: str, subject: str = "Notification") -> None:
    if not email:
        raise ValueError("L'adresse email est requise.")
    if not message:
        raise ValueError("Le message est requis.")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
        <style>
            body {{
                background-color: #f3f4f6;
                font-family: Arial, sans-serif;
                padding: 20px;
            }}
            .container {{
                background-color: #ffffff;
                padding: 20px;
                border-radius: 8px;
                max-width: 600px;
                margin: auto;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                text-align: left;
            }}
            p {{
                font-size: 16px;
                color: #111827;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <p>{message}</p>
        </div>
    </body>
    </html>
    """

    text_content = strip_tags(html_content)

    from_email = settings.EMAIL_HOST_USER or "noreply@azotin.local"
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[email],
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send()
