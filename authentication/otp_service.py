from typing import Dict, Tuple

import requests


def send_otp(phone_number: str, api_key: str, app_id: str) -> Tuple[bool, Dict]:
    """
    Envoie un code OTP au numéro de téléphone spécifié.

    Args:
        phone_number (str): Le numéro de téléphone au format international (ex: "22962585015")
        api_key (str): La clé API Our Voice
        app_id (str): L'ID de l'application

    Returns:
        Tuple[bool, Dict]: (succès, réponse)
            - succès: True si l'envoi a réussi, False sinon
            - réponse: La réponse de l'API ou le message d'erreur
    """
    # Vérification des paramètres requis
    if not phone_number:
        return False, {"error": "Le numéro de téléphone est requis"}
    if not api_key:
        return False, {"error": "La clé API GetOurVoice est requise"}
    if not app_id:
        return False, {"error": "L'ID de l'application GetOurVoice est requis"}

    base_url = "https://api.getourvoice.com"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"{base_url}/v1/otp/send"
    payload = {"send_to": phone_number, "app_id": app_id}

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        
        if response.status_code == 405:
            return False, {"error": "Méthode non autorisée. Vérifiez l'URL de l'API."}
        elif response.status_code == 401:
            return False, {"error": "Non autorisé. Vérifiez votre clé API."}
        elif response.status_code == 422:
            return False, {"error": "Données invalides. Vérifiez le format du numéro de téléphone."}
        
        response.raise_for_status()
        return True, response.json()

    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e, "response") and hasattr(e.response, "text"):
            error_message = f"{error_message} - {e.response.text}"
        return False, {"error": f"Erreur lors de l'envoi : {error_message}"}


def verify_otp(phone_number: str, code: str, api_key: str, app_id: str) -> Tuple[bool, Dict]:
    """
    Vérifie le code OTP saisi par l'utilisateur.

    Args:
        phone_number (str): Le numéro de téléphone au format international
        code (str): Le code OTP saisi par l'utilisateur
        api_key (str): La clé API Our Voice
        app_id (str): L'ID de l'application

    Returns:
        Tuple[bool, Dict]: (succès, réponse)
            - succès: True si la vérification a réussi, False sinon
            - réponse: La réponse de l'API ou le message d'erreur
    """
    if not api_key or not app_id:
        return False, {"error": "API key et APP ID sont requis"}

    base_url = "https://api.getourvoice.com"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    endpoint = f"{base_url}/v1/otp/verify"
    payload = {"code": code, "send_to": phone_number, "app_id": app_id}

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        
        if response.status_code == 405:
            return False, {"error": "Méthode non autorisée. Vérifiez l'URL de l'API."}
        elif response.status_code == 401:
            return False, {"error": "Non autorisé. Vérifiez votre clé API."}
        elif response.status_code == 422:
            return False, {"error": "Données invalides. Vérifiez le format du code ou du numéro."}
        
        response.raise_for_status()
        response_data = response.json()

        # Vérifier le succès et la validité selon la réponse de GetOurVoice
        is_valid = (
            response_data.get("success", False) and 
            response_data.get("valid", False) and 
            response_data.get("data", {}).get("status") == "verified"
        )

        return is_valid, response_data

    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e, "response") and hasattr(e.response, "text"):
            error_message = f"{error_message} - {e.response.text}"
        return False, {"error": f"Erreur lors de la vérification : {error_message}"}
