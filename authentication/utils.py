from PIL import Image
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings

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
    image = image.convert('RGB')
    
    # Enregistrer l'image convertie en JPEG
    image.save(image_path, format='JPEG')

def send_password_reset_email(email, otp_code):
    """
    Envoie un email de réinitialisation de mot de passe.

    :param email: Adresse email du destinataire.
    :param otp_code: Code OTP pour la réinitialisation du mot de passe.
    """
    subject = 'Password Reset Request'
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset Request</title>
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
            <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">Password Reset Request</h2>
            <p>Hello,</p>
            <p>We received a request to reset your password. Your OTP is:</p>
            <p class="otp-code">{otp_code}</p>
            <p style="margin-top: 20px;">If you did not request this, you can safely ignore this email.</p>
            <p>Regards,<br>The ConnectMe Team</p>
        </div>
    </body>
    </html>
    """
    text_content = strip_tags(html_content)  # Strip the HTML tags to get the text version
    email = EmailMultiAlternatives(subject, text_content, from_email=settings.EMAIL_HOST_USER, to=[email])
    email.attach_alternative(html_content, "text/html")
    email.send()

def send_activation_email(email, otp_code, activation_link):
    """
    Envoie un email d'activation de compte.

    :param email: Adresse email du destinataire.
    :param otp_code: Code OTP pour l'activation du compte.
    :param activation_link: Lien d'activation du compte.
    """
    subject = 'Activate Your Account'
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Activate Your Account</title>
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
            <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">Activate Your Account</h2>
            <p>Hello,</p>
            <p>Thank you for registering with ConnectMe. Your OTP for account activation is:</p>
            <p class="otp-code">{otp_code}</p>
            <hr style="margin: 20px 0;">
            or
            <hr style="margin: 20px 0;">
            <a href="{activation_link}" class="btn">Activate Account</a>
            <p style="margin-top: 20px;">This OTP is valid for 3 hours.</p>
            <p>Regards,<br>The ConnectMe Team</p>
        </div>
    </body>
    </html>
    """
    text_content = strip_tags(html_content)  # Strip the HTML tags to get the text version
    email = EmailMultiAlternatives(subject, text_content, from_email=settings.EMAIL_HOST_USER, to=[email])
    email.attach_alternative(html_content, "text/html")
    email.send()

def send_password_reset_sms(phone_number, otp_code):
    """
    Envoie un SMS de réinitialisation de mot de passe via WhatsApp.

    :param phone_number: Numéro de téléphone du destinataire.
    :param otp_code: Code OTP pour la réinitialisation du mot de passe.
    """
    subject = 'Password Reset Request via WhatsApp'
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset Request</title>
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
            <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem;">Password Reset Request</h2>
            <p>Hello,</p>
            <p>The user with the following WhatsApp number has requested to reset their password:</p>
            <p class="otp-code">{phone_number}</p>
            <p>The OTP for password reset is:</p>
            <p class="otp-code">{otp_code}</p>
            <p style="margin-top: 20px;">This OTP is valid for 3 hours.</p>
            <p>Regards,<br>The ConnectMe Team</p>
        </div>
    </body>
    </html>
    """
    text_content = strip_tags(html_content)  # Strip the HTML tags to get the text version
    email = EmailMultiAlternatives(subject, text_content, from_email=settings.EMAIL_HOST_USER, to=['david1anato@gmail.com'])
    email.attach_alternative(html_content, "text/html")
    email.send()
