from typing import Dict, Tuple

import requests
from django.conf import settings

GETOURVOICE_BASE_URL = "https://api.getourvoice.com"
GETOURVOICE_TIMEOUT = 15


def _otp_sms_disabled() -> bool:
    return bool(getattr(settings, "OTP_SKIP_SMS", False))


def _ourvoice_api_key() -> str:
    """GETOURVOICE_API_KEY uniquement (pas d'APP_ID). Alias OURVOICE_API_KEY conservé."""
    return (
        getattr(settings, "GETOURVOICE_API_KEY", "")
        or getattr(settings, "OURVOICE_API_KEY", "")
        or ""
    )


def otp_service_ready() -> bool:
    """True si le bypass DEV est actif ou si GETOURVOICE_API_KEY est présente."""
    if _otp_sms_disabled():
        return True
    return bool(_ourvoice_api_key())


def _dev_otp_code() -> str:
    return getattr(settings, "DEV_OTP_CODE", "00000")


def _gov_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def send_otp(phone_number: str, api_key: str = "") -> Tuple[bool, Dict]:
    """
    Envoie un code OTP au numéro de téléphone spécifié.

    Auth GetOurVoice : Bearer GETOURVOICE_API_KEY uniquement.
    Le corps ne contient pas d'app_id.

    Args:
        phone_number (str): Le numéro de téléphone au format international (ex: "22962585015")
        api_key (str): La clé API GetOurVoice (GETOURVOICE_API_KEY)

    Returns:
        Tuple[bool, Dict]: (succès, réponse)
            - succès: True si l'envoi a réussi, False sinon
            - réponse: La réponse de l'API ou le message d'erreur
    """
    if _otp_sms_disabled():
        return True, {
            "message": "SMS OTP désactivé (mode développement).",
            "dev_otp": _dev_otp_code(),
        }

    api_key = api_key or _ourvoice_api_key()

    if not phone_number:
        return False, {"error": "Le numéro de téléphone est requis"}
    if not api_key:
        return False, {
            "error": "La clé API GetOurVoice (GETOURVOICE_API_KEY) est manquante.",
            "code": "otp_service_unavailable",
        }

    endpoint = f"{GETOURVOICE_BASE_URL}/v1/otp/send"
    payload = {"send_to": phone_number}

    try:
        response = requests.post(
            endpoint,
            headers=_gov_headers(api_key),
            json=payload,
            timeout=GETOURVOICE_TIMEOUT,
        )

        if response.status_code == 405:
            return False, {"error": "Méthode non autorisée. Vérifiez l'URL de l'API."}
        elif response.status_code == 401:
            return False, {"error": "Non autorisé. Vérifiez votre clé API."}
        elif response.status_code == 422:
            return False, {
                "error": "Données invalides. Vérifiez le format du numéro de téléphone."
            }

        response.raise_for_status()
        return True, response.json()

    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e, "response") and hasattr(e.response, "text"):
            error_message = f"{error_message} - {e.response.text}"
        return False, {"error": f"Erreur lors de l'envoi : {error_message}"}


def verify_otp(phone_number: str, code: str, api_key: str = "") -> Tuple[bool, Dict]:
    """
    Vérifie le code OTP saisi par l'utilisateur.

    Auth GetOurVoice : Bearer GETOURVOICE_API_KEY uniquement.
    Le corps ne contient pas d'app_id.

    Args:
        phone_number (str): Le numéro de téléphone au format international
        code (str): Le code OTP saisi par l'utilisateur
        api_key (str): La clé API GetOurVoice (GETOURVOICE_API_KEY)

    Returns:
        Tuple[bool, Dict]: (succès, réponse)
            - succès: True si la vérification a réussi, False sinon
            - réponse: La réponse de l'API ou le message d'erreur
    """
    if _otp_sms_disabled():
        if code == _dev_otp_code():
            return True, {
                "success": True,
                "valid": True,
                "message": "Code validé (mode développement).",
                "data": {"status": "verified"},
            }
        return False, {"error": "Code OTP invalide."}

    api_key = api_key or _ourvoice_api_key()
    if not api_key:
        return False, {
            "error": "Le service OTP GetOurVoice n'est pas configuré "
            "(GETOURVOICE_API_KEY).",
            "code": "otp_service_unavailable",
        }

    endpoint = f"{GETOURVOICE_BASE_URL}/v1/otp/verify"
    payload = {"code": code, "send_to": phone_number}

    try:
        response = requests.post(
            endpoint,
            headers=_gov_headers(api_key),
            json=payload,
            timeout=GETOURVOICE_TIMEOUT,
        )

        if response.status_code == 405:
            return False, {"error": "Méthode non autorisée. Vérifiez l'URL de l'API."}
        elif response.status_code == 401:
            return False, {"error": "Non autorisé. Vérifiez votre clé API."}
        elif response.status_code == 422:
            return False, {
                "error": "Données invalides. Vérifiez le format du code ou du numéro."
            }

        response.raise_for_status()
        response_data = response.json()

        is_valid = (
            response_data.get("success", False)
            and response_data.get("valid", False)
            and response_data.get("data", {}).get("status") == "verified"
        )

        return is_valid, response_data

    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if hasattr(e, "response") and hasattr(e.response, "text"):
            error_message = f"{error_message} - {e.response.text}"
        return False, {"error": f"Erreur lors de la vérification : {error_message}"}
