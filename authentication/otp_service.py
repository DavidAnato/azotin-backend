from typing import Dict

import requests


def send_otp(phone_number: str, api_key: str, app_id: str) -> Dict:
    """
    Envoie un code OTP au numéro de téléphone spécifié.

    Args:
        phone_number (str): Le numéro de téléphone au format international (ex: "22962585015")
        api_key (str): La clé API Our Voice
        app_id (str): L'ID de l'application

    Returns:
        Dict: La réponse de l'API contenant les détails de l'envoi
    """
    base_url = "https://api.getourvoice.com"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"{base_url}/v1/otp/send"
    payload = {"send_to": phone_number, "app_id": app_id}

    try:
        print(f"Tentative d'envoi à {phone_number}...")
        response = requests.post(endpoint, headers=headers, json=payload)

        if response.status_code == 405:
            print("Erreur : Méthode non autorisée. Vérifiez l'URL de l'API.")
        elif response.status_code == 401:
            print("Erreur : Non autorisé. Vérifiez votre clé API.")
        elif response.status_code == 422:
            print(
                "Erreur : Données invalides. Vérifiez le format du numéro de téléphone."
            )
        else:
            response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'envoi : {e}")
        if hasattr(e, "response") and hasattr(e.response, "text"):
            print(f"Réponse du serveur : {e.response.text}")
        raise


def verify_otp(phone_number: str, code: str, api_key: str, app_id: str) -> Dict:
    """
    Vérifie le code OTP saisi par l'utilisateur.

    Args:
        phone_number (str): Le numéro de téléphone au format international
        code (str): Le code OTP saisi par l'utilisateur
        api_key (str): La clé API Our Voice
        app_id (str): L'ID de l'application

    Returns:
        Dict: La réponse de l'API contenant le résultat de la vérification
    """
    base_url = "https://api.getourvoice.com"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"{base_url}/v1/otp/verify"
    payload = {"code": code, "send_to": phone_number, "app_id": app_id}

    try:
        print(f"Tentative de vérification pour {phone_number}...")
        response = requests.post(endpoint, headers=headers, json=payload)

        if response.status_code == 405:
            print("Erreur : Méthode non autorisée. Vérifiez l'URL de l'API.")
        elif response.status_code == 401:
            print("Erreur : Non autorisé. Vérifiez votre clé API.")
        elif response.status_code == 422:
            print(
                "Erreur : Données invalides. Vérifiez le format du numéro de téléphone ou du code."
            )
        else:
            response.raise_for_status()

        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la vérification : {e}")
        if hasattr(e, "response") and hasattr(e.response, "text"):
            print(f"Réponse du serveur : {e.response.text}")
        raise
