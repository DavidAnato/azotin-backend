import logging
import re
from typing import Dict, Optional, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Doc : https://api-docs.getourvoice.com/otp
GETOURVOICE_BASE_URL = "https://api.getourvoice.com/v1"
GETOURVOICE_TIMEOUT = 15
_MAX_ERROR_BODY = 500

# Canal OTP GetOurVoice : SMS uniquement (whatsapp ignoré / forcé sms).
OTP_CHANNELS = ("sms",)
DEFAULT_OTP_CHANNEL = "sms"


def normalize_otp_channel(channel: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Retourne (channel, erreur). Défaut sms. WhatsApp ignoré (forcé sms)."""
    if channel is None or str(channel).strip() == "":
        return DEFAULT_OTP_CHANNEL, None
    value = str(channel).strip().lower()
    if value == "whatsapp":
        return DEFAULT_OTP_CHANNEL, None
    if value not in OTP_CHANNELS:
        return "", "channel doit être sms."
    return value, None


def _otp_delivery_skipped() -> bool:
    """OTP_SKIP_SMS=True : aucun envoi GetOurVoice."""
    return bool(getattr(settings, "OTP_SKIP_SMS", False))


def _ourvoice_api_key() -> str:
    """GETOURVOICE_API_KEY (alias OURVOICE_API_KEY). Jamais loggée."""
    return (
        getattr(settings, "GETOURVOICE_API_KEY", "")
        or getattr(settings, "OURVOICE_API_KEY", "")
        or ""
    ).strip()


def _app_id() -> str:
    return (getattr(settings, "GETOURVOICE_APP_ID", "") or "").strip()


def _app_name() -> str:
    return (getattr(settings, "GETOURVOICE_APP_NAME", "") or "").strip()


def otp_service_ready() -> bool:
    """True si le bypass DEV est actif ou si GETOURVOICE_API_KEY est présente."""
    if _otp_delivery_skipped():
        return True
    return bool(_ourvoice_api_key())


def _dev_otp_code() -> str:
    return getattr(settings, "DEV_OTP_CODE", "00000")


def _gov_headers(api_key: str) -> Dict[str, str]:
    # Doc : Authorization Bearer + Accept/Content-Type JSON (pas X-Api-Key).
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _normalize_phone(phone_number: str) -> str:
    """Doc : send_to sans + ni espaces (ex. 22962585015)."""
    if not phone_number:
        return ""
    return re.sub(r"[^\d]", "", str(phone_number).strip())


def _phone_for_log(phone_number: str) -> str:
    digits = _normalize_phone(phone_number)
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def _redact(text: str, api_key: str = "") -> str:
    if not text:
        return ""
    key = api_key or _ourvoice_api_key()
    if key:
        text = text.replace(key, "[redacted]")
    return text


def _safe_response_excerpt(response: requests.Response, api_key: str = "") -> str:
    try:
        text = (response.text or "")[:_MAX_ERROR_BODY]
    except Exception:
        return ""
    return _redact(text, api_key)


def _otp_payload(phone_number: str, extra: Optional[Dict] = None) -> Dict:
    """
    Corps officiel POST /v1/otp/send et /v1/otp/verify :
    send_to + (app_id XOR app_name). Pas de champ to/phone/sender.
    channel=sms uniquement ; pas via/provider.
    """
    payload: Dict = {"send_to": _normalize_phone(phone_number)}
    if extra:
        payload.update(extra)
    app_id = _app_id()
    app_name = _app_name()
    if app_id:
        payload["app_id"] = app_id
        if app_name:
            logger.warning(
                "GETOURVOICE_APP_ID et GETOURVOICE_APP_NAME sont définis ; "
                "seul app_id est envoyé (doc : pas les deux)."
            )
    elif app_name:
        payload["app_name"] = app_name
    else:
        logger.warning(
            "OTP GetOurVoice : ni GETOURVOICE_APP_ID ni GETOURVOICE_APP_NAME. "
            "La doc exige l'un des deux pour /v1/otp/send et /v1/otp/verify."
        )
    return payload


def _http_error_payload(
    response: requests.Response,
    action: str,
    api_key: str = "",
    phone_number: str = "",
) -> Dict:
    excerpt = _safe_response_excerpt(response, api_key)
    logger.error(
        "GetOurVoice OTP %s failed: status=%s phone=%s body=%s",
        action,
        response.status_code,
        _phone_for_log(phone_number),
        excerpt,
    )
    if response.status_code == 405:
        return {"error": "Méthode non autorisée. Vérifiez l'URL GetOurVoice (/v1/otp/…)."}
    if response.status_code == 401:
        return {"error": "Non autorisé. Vérifiez GETOURVOICE_API_KEY."}
    if response.status_code == 422:
        return {
            "error": (
                "Données invalides GetOurVoice "
                "(send_to, app_id ou app_name — voir la doc OTP)."
            ),
            "details": excerpt,
        }
    return {
        "error": f"Erreur GetOurVoice ({response.status_code}).",
        "details": excerpt,
    }


def send_otp(
    phone_number: str, api_key: str = "", channel: Optional[str] = None
) -> Tuple[bool, Dict]:
    """
    Envoie un code OTP (POST https://api.getourvoice.com/v1/otp/send).

    Auth : Bearer GETOURVOICE_API_KEY.
    Corps : send_to + (app_id XOR app_name) + channel=sms.
    OTP_SKIP_SMS=True saute l'envoi SMS (aucun appel GetOurVoice).
    """
    channel_norm, channel_error = normalize_otp_channel(channel)
    if channel_error:
        return False, {"error": channel_error}

    if _otp_delivery_skipped():
        logger.warning(
            "OTP_SKIP_SMS=True : aucun SMS GetOurVoice n'est envoyé "
            "(code DEV_OTP_CODE uniquement, channel=%s).",
            channel_norm,
        )
        return True, {
            "message": "OTP désactivé (mode développement).",
            "dev_otp": _dev_otp_code(),
            "channel": channel_norm,
        }

    api_key = (api_key or _ourvoice_api_key()).strip()
    send_to = _normalize_phone(phone_number)

    if not send_to:
        return False, {"error": "Le numéro de téléphone est requis"}
    if not api_key:
        return False, {
            "error": "La clé API GetOurVoice (GETOURVOICE_API_KEY) est manquante.",
            "code": "otp_service_unavailable",
        }

    endpoint = f"{GETOURVOICE_BASE_URL}/otp/send"
    payload = _otp_payload(send_to, extra={"channel": channel_norm})

    try:
        logger.info(
            "GetOurVoice OTP send: url=%s phone=%s channel=%s "
            "has_app_id=%s has_app_name=%s",
            endpoint,
            _phone_for_log(send_to),
            channel_norm,
            "app_id" in payload,
            "app_name" in payload,
        )
        response = requests.post(
            endpoint,
            headers=_gov_headers(api_key),
            json=payload,
            timeout=GETOURVOICE_TIMEOUT,
        )

        if response.status_code >= 400:
            return False, _http_error_payload(
                response, "send", api_key, phone_number=send_to
            )

        try:
            return True, response.json()
        except ValueError:
            logger.error(
                "GetOurVoice OTP send: réponse JSON invalide status=%s body=%s",
                response.status_code,
                _safe_response_excerpt(response, api_key),
            )
            return False, {"error": "Réponse GetOurVoice invalide (JSON)."}

    except requests.exceptions.RequestException as e:
        excerpt = ""
        if getattr(e, "response", None) is not None:
            excerpt = _safe_response_excerpt(e.response, api_key)
        logger.error(
            "GetOurVoice OTP send network error: phone=%s err=%s body=%s",
            _phone_for_log(send_to),
            _redact(str(e), api_key),
            excerpt,
        )
        return False, {"error": "Erreur réseau lors de l'envoi OTP GetOurVoice."}


def verify_otp(phone_number: str, code: str, api_key: str = "") -> Tuple[bool, Dict]:
    """
    Vérifie un code OTP (POST https://api.getourvoice.com/v1/otp/verify).

    Auth : Bearer GETOURVOICE_API_KEY.
    Corps : send_to, code, + app_id ou app_name.
    """
    if _otp_delivery_skipped():
        if str(code) == str(_dev_otp_code()):
            return True, {
                "success": True,
                "valid": True,
                "message": "Code validé (mode développement).",
                "data": {"status": "verified"},
            }
        return False, {"error": "Code OTP invalide."}

    api_key = (api_key or _ourvoice_api_key()).strip()
    send_to = _normalize_phone(phone_number)
    if not api_key:
        return False, {
            "error": "Le service OTP GetOurVoice n'est pas configuré "
            "(GETOURVOICE_API_KEY).",
            "code": "otp_service_unavailable",
        }
    if not send_to or not str(code).strip():
        return False, {"error": "Le numéro et le code OTP sont requis."}

    endpoint = f"{GETOURVOICE_BASE_URL}/otp/verify"
    payload = _otp_payload(send_to, extra={"code": str(code).strip()})

    try:
        logger.info(
            "GetOurVoice OTP verify: url=%s phone=%s has_app_id=%s has_app_name=%s",
            endpoint,
            _phone_for_log(send_to),
            "app_id" in payload,
            "app_name" in payload,
        )
        response = requests.post(
            endpoint,
            headers=_gov_headers(api_key),
            json=payload,
            timeout=GETOURVOICE_TIMEOUT,
        )

        if response.status_code >= 400:
            return False, _http_error_payload(
                response, "verify", api_key, phone_number=send_to
            )

        try:
            response_data = response.json()
        except ValueError:
            logger.error(
                "GetOurVoice OTP verify: réponse JSON invalide status=%s body=%s",
                response.status_code,
                _safe_response_excerpt(response, api_key),
            )
            return False, {"error": "Réponse GetOurVoice invalide (JSON)."}

        is_valid = (
            response_data.get("success", False)
            and response_data.get("valid", False)
            and response_data.get("data", {}).get("status") == "verified"
        )
        if not is_valid:
            logger.info(
                "GetOurVoice OTP verify: code refusé phone=%s status=%s",
                _phone_for_log(send_to),
                (response_data.get("data") or {}).get("status"),
            )
        return is_valid, response_data

    except requests.exceptions.RequestException as e:
        excerpt = ""
        if getattr(e, "response", None) is not None:
            excerpt = _safe_response_excerpt(e.response, api_key)
        logger.error(
            "GetOurVoice OTP verify network error: phone=%s err=%s body=%s",
            _phone_for_log(send_to),
            _redact(str(e), api_key),
            excerpt,
        )
        return False, {"error": "Erreur réseau lors de la vérification OTP GetOurVoice."}
