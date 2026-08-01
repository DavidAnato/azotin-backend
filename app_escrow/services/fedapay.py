"""
Service FedaPay — seule couche autorisée à parler à l'API FedaPay.

Doc officielle :
- https://docs.fedapay.com/api-reference/transactions/create
- https://docs.fedapay.com/api-reference/transactions/create-token
- https://docs.fedapay.com/integration-api/fr/webhooks-fr
- Signature : hash_hmac('sha256', f'{timestamp}.{payload}', secret) — header X-FEDAPAY-SIGNATURE
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger("app_escrow.fedapay")


class FedaPayError(Exception):
    """Erreur métier / API FedaPay."""

    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class FedaPayService:
    """Client HTTP FedaPay (sandbox / live) via secret key Bearer."""

    def __init__(self) -> None:
        env = getattr(settings, "FEDAPAY_ENVIRONMENT", "sandbox")
        if env == "live":
            self.base_url = "https://api.fedapay.com/v1"
        else:
            self.base_url = "https://sandbox-api.fedapay.com/v1"
        self.secret_key = getattr(settings, "FEDAPAY_SECRET_KEY", "") or ""
        self.public_key = getattr(settings, "FEDAPAY_PUBLIC_KEY", "") or ""
        self.webhook_secret = getattr(settings, "FEDAPAY_WEBHOOK_SECRET", "") or ""
        self.timeout = 30.0

    def _headers(self) -> dict[str, str]:
        if not self.secret_key:
            raise FedaPayError("FEDAPAY_SECRET_KEY manquante dans l'environnement")
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        logger.info("FedaPay %s %s", method.upper(), path)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method.upper(),
                    url,
                    headers=self._headers(),
                    json=json,
                )
        except httpx.HTTPError as exc:
            logger.exception("FedaPay network error: %s", exc)
            raise FedaPayError(f"Erreur réseau FedaPay: {exc}") from exc

        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {"raw": response.text}

        if response.status_code >= 400:
            logger.error(
                "FedaPay error %s %s → %s %s",
                method,
                path,
                response.status_code,
                data,
            )
            message = (
                data.get("message")
                or data.get("error")
                or f"HTTP {response.status_code}"
            )
            if response.status_code == 403 and path.rstrip("/").endswith("payouts"):
                message = (
                    f"{message}. Active les transferts/payouts sur ton compte FedaPay "
                    "(sandbox ou live), puis réessaie."
                )
            raise FedaPayError(str(message), status_code=response.status_code, payload=data)

        # L'API encapsule parfois sous "v1/transaction" / "v1/token"...
        # Ne pas perdre token/url au top-level si un wrapper v1/ coexiste.
        if isinstance(data, dict):
            if data.get("url") or data.get("token") or data.get("id"):
                return data
            for key, value in list(data.items()):
                if key.startswith("v1/") and isinstance(value, dict):
                    return value
        return data if isinstance(data, dict) else {"data": data}

    def create_transaction(
        self,
        *,
        description: str,
        amount: int,
        currency: str = "XOF",
        callback_url: str,
        customer: dict[str, Any],
        custom_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        POST /transactions
        amount en plus petite unité (XOF = entier FCFA).
        """
        payload: dict[str, Any] = {
            "description": description,
            "amount": int(amount),
            "currency": {"iso": currency},
            "callback_url": callback_url,
            "customer": customer,
        }
        if custom_metadata:
            payload["custom_metadata"] = custom_metadata
        return self._request("POST", "/transactions", json=payload)

    def get_transaction(self, transaction_id: str | int) -> dict[str, Any]:
        return self._request("GET", f"/transactions/{transaction_id}")

    def generate_payment_token(self, transaction_id: str | int) -> dict[str, Any]:
        """POST /transactions/{id}/token → { token, url }."""
        return self._request("POST", f"/transactions/{transaction_id}/token")

    def verify_payment(self, transaction_id: str | int) -> dict[str, Any]:
        """Récupère la transaction et normalise le statut."""
        tx = self.get_transaction(transaction_id)
        status = (tx.get("status") or "").lower()
        return {
            "transaction": tx,
            "status": status,
            "is_paid": status in {"approved", "transferred"},
            "amount": tx.get("amount"),
            "currency": (tx.get("currency") or {}).get("iso")
            if isinstance(tx.get("currency"), dict)
            else tx.get("currency"),
        }

    @staticmethod
    def verify_webhook_signature(
        payload: bytes | str,
        signature_header: str | None,
        secret: str,
        tolerance: int = 300,
    ) -> bool:
        """
        Vérifie X-FEDAPAY-SIGNATURE (schéma t=,s=) — algorithme officiel fedapay-php.
        signed_payload = f"{timestamp}.{payload}"
        signature = HMAC-SHA256(signed_payload, secret)
        """
        if not secret:
            raise FedaPayError("FEDAPAY_WEBHOOK_SECRET manquant")
        if not signature_header:
            raise FedaPayError("En-tête X-FEDAPAY-SIGNATURE absent")

        if isinstance(payload, bytes):
            payload_str = payload.decode("utf-8")
        else:
            payload_str = payload

        timestamp = -1
        signatures: list[str] = []
        for item in signature_header.split(","):
            parts = item.strip().split("=", 1)
            if len(parts) != 2:
                continue
            key, value = parts[0].strip(), parts[1].strip()
            if key == "t":
                try:
                    timestamp = int(value)
                except ValueError:
                    timestamp = -1
            elif key == "s":
                signatures.append(value)

        if timestamp == -1:
            raise FedaPayError("Impossible d'extraire le timestamp de la signature")
        if not signatures:
            raise FedaPayError("Aucune signature (s=) trouvée dans l'en-tête")

        signed_payload = f"{timestamp}.{payload_str}".encode("utf-8")
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        if not any(hmac.compare_digest(expected, sig) for sig in signatures):
            raise FedaPayError("Signature webhook invalide")

        if tolerance > 0 and abs(int(time.time()) - timestamp) > tolerance:
            raise FedaPayError("Timestamp webhook hors tolérance")

        return True

    def create_payout(
        self,
        *,
        amount: int,
        description: str,
        customer: dict[str, Any],
        currency: str = "XOF",
        mode: str = "mtn_open",
    ) -> dict[str, Any]:
        """POST /payouts — création d'un virement Mobile Money (mode obligatoire)."""
        payload: dict[str, Any] = {
            "amount": int(amount),
            "currency": {"iso": currency},
            "description": description,
            "mode": mode or "mtn_open",
            "customer": customer,
        }
        logger.info(
            "FedaPay create_payout amount=%s mode=%s phone=%s",
            payload["amount"],
            payload["mode"],
            (customer or {}).get("phone_number"),
        )
        return self._request("POST", "/payouts", json=payload)

    def start_payouts(self, payout_ids: list[int | str]) -> dict[str, Any]:
        """PUT /payouts/start — lance l'envoi immédiat."""
        return self._request(
            "PUT",
            "/payouts/start",
            json={"payouts": [{"id": int(pid)} for pid in payout_ids]},
        )

    def get_payout(self, payout_id: str | int) -> dict[str, Any]:
        return self._request("GET", f"/payouts/{payout_id}")


fedapay_service = FedaPayService()
