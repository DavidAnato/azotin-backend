import logging
import asyncio
import threading
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


def run_coroutine_sync(coro, timeout: float = 20.0):
    """
    Exécute une coroutine depuis un signal Django (WSGI ou ASGI/Channels).
    `run_until_complete` casse si la boucle Channels tourne déjà (push messages).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict = {}

    def _thread():
        try:
            box["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover
            box["error"] = exc

    worker = threading.Thread(target=_thread, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        logger.warning("Push Expo : timeout après %.0fs", timeout)
        return None
    if "error" in box:
        logger.warning("Push Expo : %s", box["error"])
        return None
    return box.get("value")


def _stringify_push_data(data: Optional[dict]) -> dict:
    out: dict = {}
    if not data:
        return out
    for key, value in data.items():
        if value is None:
            continue
        out[str(key)] = str(value)
    return out


async def send_push_notification(token, title, body, data=None):
    """
    Envoie une notification push à un utilisateur via Expo
    """
    if not token or not str(token).startswith("ExponentPushToken["):
        logger.warning("Token push Expo invalide")
        return None

    notification_data = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
        "priority": "high",
        "channelId": "default",
    }

    extra = _stringify_push_data(data)
    if extra:
        notification_data["data"] = extra

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://exp.host/--/api/v2/push/send",
                json=notification_data,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                result = await response.json(content_type=None)
                if response.status >= 400:
                    logger.warning("Expo push HTTP %s: %s", response.status, result)
                else:
                    status = None
                    if isinstance(result, dict):
                        status = (result.get("data") or {}).get("status")
                    if status == "error":
                        logger.warning("Expo push rejeté: %s", result)
                return result
    except Exception as e:
        logger.warning("Erreur lors de l'envoi de la notification: %s", e)
        return None


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

    from_email = (
        getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or getattr(settings, "EMAIL_HOST_USER", None)
        or "Azotin <noreply@azotin.local>"
    )
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[email],
    )
    email_message.attach_alternative(html_content, "text/html")
    email_message.send()
