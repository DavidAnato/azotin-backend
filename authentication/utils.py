import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from PIL import Image

logger = logging.getLogger(__name__)


def _from_email():
    return (
        getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or getattr(settings, "EMAIL_HOST_USER", None)
        or "Azobatin <noreply@azobatin.local>"
    )


def frontend_activation_success_url():
    base = (
        getattr(settings, "FRONTEND_URL", None) or "http://localhost:3000"
    ).rstrip("/")
    path = (
        getattr(settings, "FRONTEND_ACTIVATION_SUCCESS_PATH", None)
        or "/activation-success"
    )
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def build_activation_link(request, email, otp_code):
    query = urlencode({"otp_code": otp_code, "email": email})
    path = reverse("email-activate")
    public = (getattr(settings, "PUBLIC_API_BASE_URL", None) or "").rstrip("/")
    if public:
        return f"{public}{path}?{query}"
    if request is not None:
        return request.build_absolute_uri(f"{path}?{query}")
    return f"{path}?{query}"


def _send_html_email(subject, recipient, html_content, text_content=None):
    if not recipient:
        logger.warning("Envoi email ignoré : destinataire vide (%s)", subject)
        return False
    body = text_content or strip_tags(html_content)
    message = EmailMultiAlternatives(
        subject, body, from_email=_from_email(), to=[recipient]
    )
    message.attach_alternative(html_content, "text/html")
    try:
        message.send()
        return True
    except Exception as exc:
        logger.warning("Email « %s » non envoyé vers %s : %s", subject, recipient, exc)
        return False


def resize_and_crop(image_path, size):
    """
    Redimensionne et recadre une image pour qu'elle soit carrée.

    :param image_path: Chemin vers l'image.
    :param size: La taille du côté du carré souhaité.
    :return: Image redimensionnée et recadrée.
    """
    image = Image.open(image_path)
    width, height = image.size

    # Trouver le plus petit côté de l'image
    smallest_side = min(width, height)

    # Calculer les coordonnées pour rogner l'image au centre
    left = (width - smallest_side) / 2
    top = (height - smallest_side) / 2
    right = (width + smallest_side) / 2
    bottom = (height + smallest_side) / 2

    # Recadrer l'image
    cropped_image = image.crop((left, top, right, bottom))

    # Redimensionner l'image à la taille désirée
    resized_image = cropped_image.resize((size, size), Image.LANCZOS)

    return resized_image


def convert_png_to_jpeg(image_path):
    """
    Convertit une image PNG en JPEG.

    :param image_path: Chemin vers l'image PNG.
    """
    image = Image.open(image_path)

    # Convertir l'image en mode RGB (supprimer le canal alpha)
    image = image.convert("RGB")

    # Enregistrer l'image convertie en JPEG
    image.save(image_path, format="JPEG")


def send_password_reset_email(email, otp_code):
    """
    Envoie un email de réinitialisation de mot de passe.

    :param email: Adresse email du destinataire.
    :param otp_code: Code OTP pour la réinitialisation du mot de passe.
    :return: True si l'envoi a réussi.
    """
    context = {"otp_code": otp_code}
    html_content = render_to_string("emails/password_reset.html", context)
    text_content = render_to_string("emails/password_reset.txt", context)
    return _send_html_email(
        "Réinitialisation de votre mot de passe Azobatin",
        email,
        html_content,
        text_content,
    )


def send_activation_email(email, otp_code, activation_link):
    """
    Envoie un email d'activation / vérification de compte.

    :param email: Adresse email du destinataire.
    :param otp_code: Code OTP pour l'activation du compte.
    :param activation_link: Lien d'activation du compte.
    :return: True si l'envoi a réussi.
    """
    context = {"otp_code": otp_code, "activation_link": activation_link}
    html_content = render_to_string("emails/activation.html", context)
    text_content = render_to_string("emails/activation.txt", context)
    return _send_html_email(
        "Activez votre compte Azobatin",
        email,
        html_content,
        text_content,
    )


def send_whatsapp_message(phone_number, otp_code):
    """
    Envoie un SMS de réinitialisation de mot de passe via WhatsApp.

    :param phone_number: Numéro de téléphone du destinataire.
    :param otp_code: Code OTP pour la réinitialisation du mot de passe.
    """
    subject = "CODE OTP"
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CODE OTP</title>
        <style>
            .container {{
                max-width: 600px;
                padding: 20px;
                background-color: #ffffff;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
                margin: 0 auto;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <p style="font-size: 1.5rem; font-weight: 600;">{otp_code}</p>
        </div>
    </body>
    </html>
    """
    text_content = strip_tags(
        html_content
    )  # Strip the HTML tags to get the text version
    email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email=_from_email(),
        to=["david1anato@gmail.com"],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
