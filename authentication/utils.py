from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from PIL import Image


def _from_email():
    return (
        getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or getattr(settings, "EMAIL_HOST_USER", None)
        or "Azotin <noreply@azotin.local>"
    )


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
    """
    subject = "Réinitialisation de votre mot de passe Azotin"
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Réinitialisation de mot de passe</title>
        <style>
            body {{
                background-color: #f3f4f6;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0 auto;
            }}
            .container {{
                max-width: 600px;
                padding: 20px;
                background-color: #ffffff;
                border: 1px solid #ccc;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #007bff;
                color: #fff;
                text-decoration: none;
                border-radius: 3px;
                margin-top: 20px;
                font-size: 1.2rem;
            }}
            .otp-code {{
                font-size: 2rem;
                font-weight: 600;
                margin-top: 1.3rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">Réinitialisation de mot de passe</h2>
            <p>Bonjour,</p>
            <p>Nous avons reçu une demande de réinitialisation de votre mot de passe Azotin. Votre code est :</p>
            <p class="otp-code">{otp_code}</p>
            <p style="margin-top: 20px;">Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.</p>
            <p>Cordialement,<br>L'équipe Azotin</p>
        </div>
    </body>
    </html>
    """
    text_content = strip_tags(
        html_content
    )  # Strip the HTML tags to get the text version
    email = EmailMultiAlternatives(
        subject, text_content, from_email=_from_email(), to=[email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_activation_email(email, otp_code, activation_link):
    """
    Envoie un email d'activation de compte.

    :param email: Adresse email du destinataire.
    :param otp_code: Code OTP pour l'activation du compte.
    :param activation_link: Lien d'activation du compte.
    """
    subject = "Activez votre compte Azotin"
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Activez votre compte Azotin</title>
        <style>
            body {{
                background-color: #f3f4f6;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
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
            .otp-code {{
                font-size: 2rem;
                font-weight: 600;
                margin: 1.2rem 0;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                background-color: #007bff;
                color: #fff;
                text-decoration: none;
                border-radius: 3px;
                margin-top: 16px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Bienvenue sur Azotin</h2>
            <p>Votre code d'activation :</p>
            <p class="otp-code">{otp_code}</p>
            <p><a class="btn" href="{activation_link}">Activer mon compte</a></p>
            <p>Cordialement,<br>L'équipe Azotin</p>
        </div>
    </body>
    </html>
    """
    text_content = strip_tags(
        html_content
    )  # Strip the HTML tags to get the text version
    email = EmailMultiAlternatives(
        subject, text_content, from_email=_from_email(), to=[email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


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
