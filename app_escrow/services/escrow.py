"""
Services métier Escrow — transitions d'état, séquestre, wallet.
"""

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from app_escrow.models import (
    Contract,
    ContractStatus,
    Payment,
    PaymentStatus,
    Wallet,
    WalletTransaction,
    WalletTransactionType,
    Withdrawal,
    WithdrawalStatus,
)
from app_escrow.notifications import contract_notif_object, notify_user
from app_escrow.platform_settings import get_platform_settings
from app_escrow.services.fedapay import (
    FedaPayError,
    fedapay_service,
    normalize_fedapay_payout_mode,
)

logger = logging.getLogger("app_escrow.services")


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ContractStatus.DRAFT: {ContractStatus.PENDING, ContractStatus.CANCELLED},
    ContractStatus.PENDING: {
        ContractStatus.ACCEPTED,
        ContractStatus.CANCELLED,
    },
    ContractStatus.ACCEPTED: {
        ContractStatus.WAITING_PAYMENT,
        ContractStatus.CANCELLED,
    },
    ContractStatus.WAITING_PAYMENT: {
        ContractStatus.FUNDED,
        ContractStatus.CANCELLED,
    },
    ContractStatus.FUNDED: {ContractStatus.WORKING, ContractStatus.DISPUTE},
    ContractStatus.WORKING: {
        ContractStatus.SUBMITTED,
        ContractStatus.DISPUTE,
        ContractStatus.CANCELLED,
    },
    ContractStatus.SUBMITTED: {
        ContractStatus.COMPLETED,
        ContractStatus.REVISION,
        ContractStatus.DISPUTE,
    },
    ContractStatus.REVISION: {
        ContractStatus.WORKING,
        ContractStatus.SUBMITTED,
        ContractStatus.DISPUTE,
    },
    ContractStatus.DISPUTE: {
        ContractStatus.WORKING,
        ContractStatus.COMPLETED,
        ContractStatus.CANCELLED,
    },
}


def get_or_create_wallet(user) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(owner=user)
    return wallet


def compute_contract_commission(gross: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Retourne (fee, net, percent) en FCFA entiers."""
    platform = get_platform_settings()
    percent = Decimal(platform.commission_percent)
    gross_fcfa = Decimal(int(gross))
    fee = (gross_fcfa * percent / Decimal("100")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    net = gross_fcfa - fee
    return fee, net, percent


def _normalize_phone(phone: str) -> dict:
    """Format legacy transactions (country BJ)."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if digits.startswith("229"):
        digits = digits[3:]
    if len(digits) < 8:
        digits = "90000000"
    return {"number": digits[-10:], "country": "BJ"}


def _bj_local_digits(phone: str) -> str:
    """Extrait le numéro national BJ (8 ou 10 chiffres, éventuellement préfixe 01)."""
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if digits.startswith("229"):
        digits = digits[3:]
    return digits


def _fedapay_payout_phone(phone: str) -> dict[str, str]:
    """Numéro Bénin pour payouts FedaPay (+229…, country bj)."""
    local = _bj_local_digits(phone)
    if not local or len(local) < 8:
        local = "90000000"
    # FedaPay attend le format international complet (ex. +22997808080).
    return {"number": f"+229{local}", "country": "bj"}


def _fedapay_payout_mode(phone: str) -> str:
    """
    Mode FedaPay pour POST /payouts.
    Sandbox : momo_test (libellé dashboard « Momo Test »).
    Live : détection opérateur BJ si FEDAPAY_PAYOUT_MODE est vide.
    """
    configured = (getattr(settings, "FEDAPAY_PAYOUT_MODE", "") or "").strip()
    if configured:
        return normalize_fedapay_payout_mode(configured)

    env = (getattr(settings, "FEDAPAY_ENVIRONMENT", "sandbox") or "sandbox").lower()
    if env != "live":
        return "momo_test"

    local = _bj_local_digits(phone)
    if local.startswith("01") and len(local) >= 4:
        op = local[2:4]
    else:
        op = local[:2]
    mtn = {"97", "96", "91", "90", "61", "62", "66", "67", "51", "52", "53", "54"}
    moov = {"95", "94", "64", "65", "68", "69", "55", "56"}
    if op in moov:
        return "moov"
    if op in mtn:
        return "mtn_open"
    return "mtn_open"


def _fedapay_customer_for_user(user, phone: str) -> dict:
    return {
        "firstname": user.first_name or "Utilisateur",
        "lastname": user.last_name or "Azotin",
        "email": user.email or f"user{user.id}@azotin.app",
        "phone_number": _fedapay_payout_phone(phone),
    }


def _assert_transition(contract: Contract, new_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(contract.status, set())
    if new_status not in allowed and new_status != contract.status:
        raise ValidationError(
            f"Transition invalide: {contract.status} → {new_status}"
        )


def _is_real_fedapay_tx_id(tx_id: str | None) -> bool:
    """Les seeds utilisent 'seed-tx-N' — seuls les IDs numériques FedaPay sont réutilisables."""
    return bool(tx_id) and str(tx_id).isdigit()


def _sync_linked_job(contract: Contract) -> None:
    """Aligne Job.completed sur le statut du contrat escrow."""
    if not contract.job_id:
        return
    try:
        from app_job.models import Job

        job = Job.objects.filter(pk=contract.job_id).first()
        if not job:
            return
        should_complete = contract.status == ContractStatus.COMPLETED
        if job.completed != should_complete:
            job.completed = should_complete
            job.save(update_fields=["completed", "updated_at"])
    except Exception:  # noqa: BLE001
        logger.exception(
            "Échec sync Job#%s pour contrat #%s", contract.job_id, contract.id
        )


def _cancel_pending_payment(payment: Payment, status: str = PaymentStatus.CANCELED) -> None:
    with transaction.atomic():
        payment.status = status
        payment.save(update_fields=["status", "updated_at"])


@transaction.atomic
def accept_contract(contract: Contract, user) -> Contract:
    if contract.freelancer_id != user.id:
        raise PermissionDenied("Seul le freelance peut accepter ce contrat.")
    _assert_transition(contract, ContractStatus.ACCEPTED)
    contract.status = ContractStatus.ACCEPTED
    contract.save(update_fields=["status", "updated_at"])
    return contract


def fund_contract(contract: Contract, user, callback_url: str) -> tuple[Contract, Payment]:
    """
    Crée / rafraîchit un paiement FedaPay.
    Important : les appels HTTP FedaPay sont HORS transaction DB pour éviter
    sqlite 'database is locked' (webhooks ngrok concurrents).
    """
    if contract.client_id != user.id:
        raise PermissionDenied("Seul le client peut financer ce contrat.")

    # Déjà financé (webhook/callback) — le client peut re-poller sans erreur.
    if contract.status in {
        ContractStatus.FUNDED,
        ContractStatus.WORKING,
        ContractStatus.SUBMITTED,
        ContractStatus.REVISION,
        ContractStatus.COMPLETED,
    }:
        payment = contract.payments.order_by("-created_at").first()
        if payment is None:
            raise ValidationError("Contrat financé sans paiement associé.")
        return contract, payment

    if contract.status not in {
        ContractStatus.ACCEPTED,
        ContractStatus.WAITING_PAYMENT,
    }:
        raise ValidationError("Le contrat doit être accepté avant financement.")

    existing = (
        contract.payments.filter(status=PaymentStatus.PENDING)
        .exclude(fedapay_transaction_id="")
        .order_by("-created_at")
        .first()
    )

    if existing and _is_real_fedapay_tx_id(existing.fedapay_transaction_id):
        # Vérifie l'état réel chez FedaPay avant de recycler le token
        remote_status = "unknown"
        verified_payload = None
        try:
            verified = fedapay_service.verify_payment(existing.fedapay_transaction_id)
            remote_status = (verified.get("status") or "").lower()
            verified_payload = verified.get("transaction")
        except FedaPayError:
            logger.exception(
                "Impossible de vérifier tx %s — nouvelle transaction",
                existing.fedapay_transaction_id,
            )

        if remote_status in {"approved", "transferred"}:
            # Payé chez FedaPay mais pas sync local (webhook/callback raté)
            mark_contract_funded(existing, transaction_payload=verified_payload)
            contract.refresh_from_db()
            existing.refresh_from_db()
            return contract, existing

        if remote_status in {"declined", "canceled", "cancelled", "refunded"}:
            _cancel_pending_payment(
                existing,
                PaymentStatus.DECLINED
                if remote_status == "declined"
                else PaymentStatus.CANCELED,
            )
        elif remote_status == "pending":
            try:
                token_data = fedapay_service.generate_payment_token(
                    existing.fedapay_transaction_id
                )
                new_url = (token_data.get("url") or "").strip()
                if not new_url:
                    raise FedaPayError("Token FedaPay sans URL")
                with transaction.atomic():
                    existing.payment_url = new_url
                    existing.payment_token = (
                        token_data.get("token") or existing.payment_token
                    )
                    existing.raw_response = {
                        **(existing.raw_response or {}),
                        "token_refresh": token_data,
                    }
                    existing.save(
                        update_fields=[
                            "payment_url",
                            "payment_token",
                            "raw_response",
                            "updated_at",
                        ]
                    )
                    contract.status = ContractStatus.WAITING_PAYMENT
                    contract.save(update_fields=["status", "updated_at"])
                return contract, existing
            except FedaPayError:
                logger.exception(
                    "Échec refresh token paiement %s — nouvelle transaction",
                    existing.id,
                )
                _cancel_pending_payment(existing)
        else:
            # unknown / expired → ne pas recycler une URL morte (page triangle FedaPay)
            _cancel_pending_payment(existing)
    elif existing:
        logger.warning(
            "Paiement pending non-FedaPay ignoré (tx=%s)",
            existing.fedapay_transaction_id,
        )
        _cancel_pending_payment(existing)

    amount = int(contract.amount)
    customer = {
        "firstname": user.first_name or "Client",
        "lastname": user.last_name or "Azotin",
        "email": user.email or f"user{user.id}@azotin.local",
        "phone_number": _normalize_phone(getattr(user, "phone_number", "") or ""),
    }

    try:
        tx = fedapay_service.create_transaction(
            description=f"Escrow contrat #{contract.id} — {contract.title}",
            amount=amount,
            currency=contract.currency or "XOF",
            callback_url=callback_url,
            customer=customer,
            custom_metadata={
                "contract_id": contract.id,
                "client_id": contract.client_id,
                "freelancer_id": contract.freelancer_id,
            },
        )
        tx_id = tx.get("id")
        token_data = fedapay_service.generate_payment_token(tx_id)
    except FedaPayError as exc:
        logger.exception("Échec création paiement contrat %s", contract.id)
        raise ValidationError(str(exc)) from exc

    payment_url = (token_data.get("url") or "").strip()
    payment_token = (token_data.get("token") or "").strip()
    if not payment_url:
        raise ValidationError("FedaPay n'a pas renvoyé d'URL de paiement.")

    with transaction.atomic():
        payment = Payment.objects.create(
            contract=contract,
            fedapay_transaction_id=str(tx_id),
            fedapay_reference=str(tx.get("reference") or ""),
            amount=contract.amount,
            currency=contract.currency,
            status=PaymentStatus.PENDING,
            payment_url=payment_url,
            payment_token=payment_token,
            raw_response={"transaction": tx, "token": token_data},
        )
        contract.status = ContractStatus.WAITING_PAYMENT
        contract.save(update_fields=["status", "updated_at"])
    return contract, payment


@transaction.atomic
def mark_contract_funded(payment: Payment, transaction_payload: dict | None = None) -> Contract:
    """Appelé par webhook/callback — idempotent si déjà FUNDED/WORKING."""
    contract = (
        Contract.objects.select_for_update()
        .select_related("client", "freelancer")
        .get(pk=payment.contract_id)
    )

    if payment.status == PaymentStatus.APPROVED and contract.status in {
        ContractStatus.FUNDED,
        ContractStatus.WORKING,
        ContractStatus.SUBMITTED,
        ContractStatus.REVISION,
        ContractStatus.COMPLETED,
    }:
        return contract

    payment.status = PaymentStatus.APPROVED
    payment.paid_at = timezone.now()
    if transaction_payload:
        payment.raw_response = {
            **(payment.raw_response or {}),
            "webhook_transaction": transaction_payload,
        }
    payment.save()

    if contract.status in {
        ContractStatus.WAITING_PAYMENT,
        ContractStatus.ACCEPTED,
    }:
        contract.status = ContractStatus.FUNDED
        contract.funded_at = timezone.now()
        contract.save(update_fields=["status", "funded_at", "updated_at"])

    # Après paiement réussi → WORKING auto (mission démarrable)
    if contract.status == ContractStatus.FUNDED:
        contract.status = ContractStatus.WORKING
        contract.save(update_fields=["status", "updated_at"])

    _sync_linked_job(contract)

    notify_user(
        contract.freelancer,
        "Le client a payé. Tu peux commencer.",
        kind="contract_funded",
        object=contract_notif_object(contract),
        push_title="Mission payée",
    )
    notify_user(
        contract.client,
        "Paiement confirmé.",
        kind="payment_confirmed",
        object=contract_notif_object(contract),
        push_title="Paiement confirmé",
    )
    return contract


@transaction.atomic
def start_working(contract: Contract, user) -> Contract:
    if contract.freelancer_id != user.id:
        raise PermissionDenied("Seul le freelance peut démarrer le travail.")
    if contract.status == ContractStatus.FUNDED:
        _assert_transition(contract, ContractStatus.WORKING)
        contract.status = ContractStatus.WORKING
        contract.save(update_fields=["status", "updated_at"])
    elif contract.status != ContractStatus.WORKING:
        raise ValidationError("Le contrat doit être financé.")
    return contract


@transaction.atomic
def submit_deliverable(
    contract: Contract,
    user,
    *,
    note: str = "",
    url: str = "",
    audio=None,
    image=None,
) -> Contract:
    if contract.freelancer_id != user.id:
        raise PermissionDenied("Seul le freelance peut soumettre un livrable.")
    if contract.status == ContractStatus.FUNDED:
        contract.status = ContractStatus.WORKING
        contract.save(update_fields=["status", "updated_at"])
    if contract.status not in {ContractStatus.WORKING, ContractStatus.REVISION}:
        raise ValidationError("Soumission impossible dans cet état.")
    contract.deliverable_note = note
    contract.deliverable_url = url or ""
    if audio is not None:
        contract.deliverable_audio = audio
    if image is not None:
        contract.deliverable_image = image
    contract.status = ContractStatus.SUBMITTED
    update_fields = [
        "deliverable_note",
        "deliverable_url",
        "status",
        "updated_at",
    ]
    if audio is not None:
        update_fields.append("deliverable_audio")
    if image is not None:
        update_fields.append("deliverable_image")
    contract.save(update_fields=update_fields)

    contract = Contract.objects.select_related("client", "freelancer").get(
        pk=contract.pk
    )
    notify_user(
        contract.client,
        "Le prestataire a envoyé son travail.",
        kind="deliverable_submitted",
        object=contract_notif_object(contract),
        push_title="Travail reçu",
    )
    return contract


@transaction.atomic
def approve_contract(contract: Contract, user) -> Contract:
    """Client accepte → COMPLETED + crédit wallet freelance (net après commission)."""
    if contract.client_id != user.id:
        raise PermissionDenied("Seul le client peut approuver le livrable.")
    _assert_transition(contract, ContractStatus.COMPLETED)

    platform_fee, freelancer_net, percent = compute_contract_commission(
        Decimal(contract.amount)
    )

    contract.status = ContractStatus.COMPLETED
    contract.completed_at = timezone.now()
    contract.platform_fee = platform_fee
    contract.freelancer_net = freelancer_net
    contract.save(
        update_fields=[
            "status",
            "completed_at",
            "platform_fee",
            "freelancer_net",
            "updated_at",
        ]
    )

    wallet = get_or_create_wallet(contract.freelancer)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

    # Évite double crédit
    already = WalletTransaction.objects.filter(
        wallet=wallet,
        contract=contract,
        type=WalletTransactionType.ESCROW_RELEASE,
    ).exists()
    if not already:
        wallet.balance = Decimal(wallet.balance) + freelancer_net
        wallet.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=wallet,
            type=WalletTransactionType.ESCROW_RELEASE,
            amount=freelancer_net,
            reason=(
                f"Libération séquestre contrat #{contract.id} "
                f"(commission {percent}% : {int(platform_fee)} FCFA)"
            ),
            contract=contract,
            balance_after=wallet.balance,
        )
        if platform_fee > 0:
            WalletTransaction.objects.create(
                wallet=wallet,
                type=WalletTransactionType.PLATFORM_FEE,
                amount=platform_fee,
                reason=f"Commission plateforme {percent}% — contrat #{contract.id}",
                contract=contract,
                balance_after=wallet.balance,
            )
    _sync_linked_job(contract)

    contract = Contract.objects.select_related("client", "freelancer").get(
        pk=contract.pk
    )
    currency = contract.currency or "XOF"
    amount_label = f"{int(freelancer_net)} {currency}"
    notify_user(
        contract.freelancer,
        f"Travail validé. {amount_label} sont sur ton portefeuille.",
        kind="contract_completed",
        object=contract_notif_object(
            contract, amount=str(freelancer_net), currency=currency
        ),
        push_title="Mission terminée",
    )
    return contract


@transaction.atomic
def request_revision(contract: Contract, user, note: str) -> Contract:
    if contract.client_id != user.id:
        raise PermissionDenied("Seul le client peut demander une révision.")
    _assert_transition(contract, ContractStatus.REVISION)
    contract.status = ContractStatus.REVISION
    contract.revision_note = note
    contract.save(update_fields=["status", "revision_note", "updated_at"])

    contract = Contract.objects.select_related("client", "freelancer").get(
        pk=contract.pk
    )
    notify_user(
        contract.freelancer,
        "Le client te demande de modifier ton travail.",
        kind="revision_requested",
        object=contract_notif_object(contract),
        push_title="Modification demandée",
    )
    return contract


@transaction.atomic
def open_dispute(contract: Contract, user, reason: str) -> Contract:
    if user.id not in {contract.client_id, contract.freelancer_id}:
        raise PermissionDenied("Accès refusé.")
    if contract.status in {
        ContractStatus.COMPLETED,
        ContractStatus.CANCELLED,
        ContractStatus.DRAFT,
    }:
        raise ValidationError("Litige impossible dans cet état.")
    contract.status = ContractStatus.DISPUTE
    contract.dispute_reason = reason
    contract.save(update_fields=["status", "dispute_reason", "updated_at"])

    contract = Contract.objects.select_related("client", "freelancer").get(
        pk=contract.pk
    )
    other = (
        contract.freelancer
        if user.id == contract.client_id
        else contract.client
    )
    notify_user(
        other,
        "Un problème a été signalé sur le contrat.",
        kind="dispute_opened",
        object=contract_notif_object(contract),
        push_title="Problème signalé",
    )
    return contract


@transaction.atomic
def _refund_failed_withdrawal(withdrawal: Withdrawal, error_message: str) -> None:
    wallet = Wallet.objects.select_for_update().get(pk=withdrawal.wallet_id)
    wallet.balance = Decimal(wallet.balance) + Decimal(withdrawal.amount)
    wallet.save(update_fields=["balance", "updated_at"])
    withdrawal.status = WithdrawalStatus.FAILED
    withdrawal.error_message = (error_message or "")[:2000]
    withdrawal.processed_at = timezone.now()
    withdrawal.save(
        update_fields=[
            "status",
            "error_message",
            "processed_at",
            "fedapay_status",
            "updated_at",
        ]
    )
    WalletTransaction.objects.create(
        wallet=wallet,
        type=WalletTransactionType.REFUND,
        amount=withdrawal.amount,
        reason=f"Remboursement retrait #{withdrawal.id} (échec payout)",
        balance_after=wallet.balance,
    )
    owner = wallet.owner
    notify_user(
        owner,
        "Ton retrait a échoué. L’argent est revenu sur ton portefeuille.",
        kind="withdrawal_failed",
        object={
            "withdrawal_id": withdrawal.id,
            "amount": str(withdrawal.amount),
            "currency": wallet.currency or "XOF",
        },
        push_title="Retrait échoué",
    )


def _execute_fedapay_payout(withdrawal: Withdrawal, user) -> Withdrawal:
    wallet = withdrawal.wallet
    phone = withdrawal.phone_number or getattr(user, "phone_number", "") or ""
    customer = _fedapay_customer_for_user(user, phone)
    mode = _fedapay_payout_mode(phone)
    balance = getattr(settings, "FEDAPAY_TRANSFER_BALANCE", "") or ""
    try:
        payout = fedapay_service.create_payout(
            amount=int(withdrawal.amount),
            description=f"Retrait AZOTIN #{withdrawal.id}",
            customer=customer,
            currency=wallet.currency or "XOF",
            mode=mode,
            balance=balance,
        )
        payout_id = payout.get("id")
        if payout_id is None:
            raise FedaPayError("FedaPay n'a pas renvoyé d'ID de payout")
        fedapay_service.start_payouts([payout_id])
        fedapay_status = str(payout.get("status") or "pending").lower()
        withdrawal.fedapay_payout_id = str(payout_id)
        withdrawal.fedapay_status = fedapay_status
        withdrawal.status = WithdrawalStatus.PROCESSING
        withdrawal.save(
            update_fields=[
                "fedapay_payout_id",
                "fedapay_status",
                "status",
                "updated_at",
            ]
        )
    except FedaPayError as exc:
        logger.exception("Échec payout FedaPay retrait %s", withdrawal.id)
        _refund_failed_withdrawal(withdrawal, str(exc))
        raise ValidationError(str(exc)) from exc
    return withdrawal


def apply_payout_webhook(entity: dict, event_name: str = "") -> None:
    """Met à jour un retrait depuis un webhook FedaPay payout."""
    payout_id = str(entity.get("id") or "")
    if not payout_id:
        return
    withdrawal = (
        Withdrawal.objects.filter(fedapay_payout_id=payout_id)
        .select_related("wallet")
        .first()
    )
    if withdrawal is None:
        logger.warning("Retrait introuvable pour payout FedaPay %s", payout_id)
        return
    if withdrawal.status in {WithdrawalStatus.COMPLETED, WithdrawalStatus.FAILED}:
        return

    fedapay_status = str(entity.get("status") or "").lower()
    withdrawal.fedapay_status = fedapay_status or withdrawal.fedapay_status

    success_events = {"payout.sent", "payout.completed", "payout.transferred"}
    fail_events = {"payout.failed", "payout.canceled", "payout.cancelled"}

    if event_name in success_events or fedapay_status in {
        "sent",
        "completed",
        "transferred",
    }:
        withdrawal.status = WithdrawalStatus.COMPLETED
        withdrawal.processed_at = timezone.now()
        withdrawal.save(
            update_fields=[
                "status",
                "fedapay_status",
                "processed_at",
                "updated_at",
            ]
        )
        owner = withdrawal.wallet.owner
        currency = withdrawal.wallet.currency or "XOF"
        notify_user(
            owner,
            f"Retrait de {int(withdrawal.amount)} {currency} envoyé sur ton Mobile Money.",
            kind="withdrawal_completed",
            object={
                "withdrawal_id": withdrawal.id,
                "amount": str(withdrawal.amount),
                "currency": currency,
            },
            push_title="Retrait envoyé",
        )
        return

    if event_name in fail_events or fedapay_status == "failed":
        msg = (
            entity.get("failure_message")
            or entity.get("message")
            or "Payout Mobile Money échoué"
        )
        _refund_failed_withdrawal(withdrawal, str(msg))
        return

    withdrawal.save(update_fields=["fedapay_status", "updated_at"])


@transaction.atomic
def request_withdrawal(user, amount: Decimal, phone_number: str = "", method: str = "mobile_money") -> Withdrawal:
    if amount <= 0:
        raise ValidationError("Montant invalide.")
    wallet = get_or_create_wallet(user)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if Decimal(wallet.balance) < Decimal(amount):
        raise ValidationError("Solde insuffisant.")

    wallet.balance = Decimal(wallet.balance) - Decimal(amount)
    wallet.save(update_fields=["balance", "updated_at"])

    withdrawal = Withdrawal.objects.create(
        wallet=wallet,
        amount=amount,
        status=WithdrawalStatus.PENDING,
        phone_number=phone_number or getattr(user, "phone_number", "") or "",
        method=method or "mobile_money",
    )
    WalletTransaction.objects.create(
        wallet=wallet,
        type=WalletTransactionType.WITHDRAWAL,
        amount=amount,
        reason=f"Demande de retrait #{withdrawal.id}",
        balance_after=wallet.balance,
    )
    notify_user(
        user,
        "Retrait en cours…",
        kind="withdrawal_requested",
        object={
            "withdrawal_id": withdrawal.id,
            "amount": str(amount),
            "currency": wallet.currency or "XOF",
        },
        push_title="Retrait",
    )
    return _execute_fedapay_payout(withdrawal, user)


def build_callback_url(contract_id: int) -> str:
    base = getattr(settings, "PUBLIC_API_BASE_URL", "").rstrip("/")
    if not base:
        base = "http://localhost:8000"
    return f"{base}/api/payments/fedapay/callback/?contract_id={contract_id}"
