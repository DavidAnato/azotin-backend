"""
API Escrow + webhook FedaPay.
"""

from __future__ import annotations

import json
import logging

from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app_escrow.models import (
    Contract,
    ContractStatus,
    Payment,
    PaymentStatus,
    WalletTransaction,
    WebhookEventLog,
)
from app_escrow.serializers import (
    ContractCreateSerializer,
    ContractSerializer,
    DisputeSerializer,
    PaymentSerializer,
    RevisionSerializer,
    SubmitDeliverableSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
    WithdrawalCreateSerializer,
    WithdrawalSerializer,
)
from app_escrow.services.escrow import (
    _is_real_fedapay_tx_id,
    accept_contract,
    apply_payout_webhook,
    approve_contract,
    build_callback_url,
    fund_contract,
    get_or_create_wallet,
    open_dispute,
    request_revision,
    request_withdrawal,
    start_working,
    submit_deliverable,
    mark_contract_funded,
)
from app_escrow.services.fedapay import FedaPayError, fedapay_service
from django.conf import settings

logger = logging.getLogger("app_escrow.views")


class ContractListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ContractCreateSerializer
        return ContractSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Contract.objects.filter(
            Q(client=user) | Q(freelancer=user)
        ).select_related("client", "freelancer")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
            if len(statuses) == 1:
                qs = qs.filter(status=statuses[0])
            elif statuses:
                qs = qs.filter(status__in=statuses)
        role = self.request.query_params.get("role")
        if role == "client":
            qs = qs.filter(client=user)
        elif role == "freelancer":
            qs = qs.filter(freelancer=user)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = serializer.save()
        return Response(
            ContractSerializer(contract).data,
            status=status.HTTP_201_CREATED,
        )


class ContractDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ContractSerializer

    def get_queryset(self):
        user = self.request.user
        return Contract.objects.filter(
            Q(client=user) | Q(freelancer=user)
        ).select_related("client", "freelancer")


class ContractPaymentStatusView(APIView):
    """GET poll-friendly : WAITING_PAYMENT n'est pas une erreur."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        contract = (
            Contract.objects.filter(Q(client=request.user) | Q(freelancer=request.user), pk=pk)
            .select_related("client", "freelancer")
            .first()
        )
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)

        payment = contract.payments.order_by("-created_at").first()
        if (
            payment
            and payment.status == PaymentStatus.PENDING
            and _is_real_fedapay_tx_id(payment.fedapay_transaction_id)
        ):
            try:
                verified = fedapay_service.verify_payment(payment.fedapay_transaction_id)
                if verified.get("is_paid"):
                    mark_contract_funded(
                        payment, transaction_payload=verified.get("transaction")
                    )
                    contract.refresh_from_db()
                    payment.refresh_from_db()
            except FedaPayError:
                logger.info(
                    "verify_payment indisponible pour contrat %s — statut local conservé",
                    contract.id,
                )

        funded_statuses = {
            ContractStatus.FUNDED,
            ContractStatus.WORKING,
            ContractStatus.SUBMITTED,
            ContractStatus.REVISION,
            ContractStatus.COMPLETED,
        }
        pending = contract.status == ContractStatus.WAITING_PAYMENT
        declined = bool(
            payment
            and payment.status
            in {PaymentStatus.DECLINED, PaymentStatus.CANCELED}
        )
        return Response(
            {
                "contract_id": contract.id,
                "contract_status": contract.status,
                "payment_status": payment.status if payment else None,
                "pending_confirmation": pending,
                "funded": contract.status in funded_statuses,
                "is_error": declined and not pending,
                "payment": PaymentSerializer(payment).data if payment else None,
                "contract": ContractSerializer(contract).data,
            }
        )


class ContractAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(
            Q(client=request.user) | Q(freelancer=request.user), pk=pk
        ).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        contract = accept_contract(contract, request.user)
        return Response(ContractSerializer(contract).data)


class ContractFundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        callback = request.data.get("callback_url") or build_callback_url(contract.id)
        contract, payment = fund_contract(contract, request.user, callback)
        return Response(
            {
                "contract": ContractSerializer(contract).data,
                "payment": PaymentSerializer(payment).data,
                "payment_url": payment.payment_url,
                "payment_id": payment.id,
                "pending_confirmation": contract.status
                == ContractStatus.WAITING_PAYMENT,
                "funded": contract.status
                in {
                    ContractStatus.FUNDED,
                    ContractStatus.WORKING,
                    ContractStatus.SUBMITTED,
                    ContractStatus.REVISION,
                    ContractStatus.COMPLETED,
                },
            }
        )


class ContractStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        contract = start_working(contract, request.user)
        return Response(ContractSerializer(contract).data)


class ContractSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        ser = SubmitDeliverableSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        contract = submit_deliverable(
            contract,
            request.user,
            note=ser.validated_data.get("deliverable_note") or "",
            url=ser.validated_data.get("deliverable_url") or "",
            audio=ser.validated_data.get("deliverable_audio"),
            image=ser.validated_data.get("deliverable_image"),
        )
        return Response(
            ContractSerializer(contract, context={"request": request}).data
        )


class ContractApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        contract = approve_contract(contract, request.user)
        return Response(ContractSerializer(contract).data)


class ContractRevisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        ser = RevisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        contract = request_revision(contract, request.user, ser.validated_data["note"])
        return Response(ContractSerializer(contract).data)


class ContractDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        contract = Contract.objects.filter(pk=pk).first()
        if not contract:
            return Response({"detail": "Introuvable"}, status=404)
        ser = DisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        contract = open_dispute(contract, request.user, ser.validated_data["reason"])
        return Response(ContractSerializer(contract).data)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        return Response(WalletSerializer(wallet).data)


class WalletHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        wallet = get_or_create_wallet(self.request.user)
        return WalletTransaction.objects.filter(wallet=wallet)


class WalletWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = WithdrawalCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        code_pin = (
            ser.validated_data.get("code_pin")
            or request.data.get("code_pin")
            or request.headers.get("X-Code-Pin")
            or request.headers.get("X-PIN")
            or ""
        )
        user = request.user
        if not user.code_pin:
            return Response(
                {
                    "detail": "Aucun code PIN défini. Définissez un PIN avant de retirer.",
                    "code": "pin_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not code_pin:
            return Response(
                {
                    "detail": "Le code PIN est requis pour retirer.",
                    "code": "pin_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if str(code_pin) != str(user.code_pin):
            return Response(
                {"detail": "Code PIN invalide.", "code": "invalid_pin"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        withdrawal = request_withdrawal(
            request.user,
            ser.validated_data["amount"],
            phone_number=ser.validated_data.get("phone_number") or "",
            method=ser.validated_data.get("method") or "mobile_money",
        )
        return Response(WithdrawalSerializer(withdrawal).data, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class FedaPayWebhookView(APIView):
    """
    POST /api/payments/fedapay/webhook/
    Vérifie X-FEDAPAY-SIGNATURE, idempotent via WebhookEventLog.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.body
        signature = request.headers.get("X-FEDAPAY-SIGNATURE") or request.META.get(
            "HTTP_X_FEDAPAY_SIGNATURE"
        )
        secret = getattr(settings, "FEDAPAY_WEBHOOK_SECRET", "") or ""

        # En sandbox sans secret configuré : log warning mais refuse en prod-like
        skip_sig = getattr(settings, "FEDAPAY_SKIP_WEBHOOK_SIGNATURE", False)
        try:
            if not skip_sig:
                fedapay_service.verify_webhook_signature(raw, signature, secret)
        except FedaPayError as exc:
            logger.warning("Webhook signature rejected: %s", exc)
            return Response({"detail": str(exc)}, status=400)

        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (ValueError, UnicodeDecodeError):
            return Response({"detail": "JSON invalide"}, status=400)

        event_name = payload.get("name") or payload.get("type") or ""
        event_id = str(
            payload.get("id")
            or payload.get("event_id")
            or f"{event_name}:{payload.get('entity', {}).get('id', '')}"
        )
        entity = payload.get("entity") or payload.get("data") or {}
        if isinstance(entity, dict) and "v1/transaction" in entity:
            entity = entity["v1/transaction"]

        if WebhookEventLog.objects.filter(event_id=event_id).exists():
            return Response({"received": True, "duplicate": True})

        try:
            self._handle_event(event_name, entity, payload)
            WebhookEventLog.objects.create(
                event_id=event_id,
                event_name=event_name,
                payload=payload,
                success=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Webhook processing error")
            WebhookEventLog.objects.create(
                event_id=event_id,
                event_name=event_name,
                payload=payload,
                success=False,
                error=str(exc),
            )
            return Response({"detail": "processing_error"}, status=500)

        return Response({"received": True})

    def _handle_event(self, event_name: str, entity: dict, payload: dict) -> None:
        payout_events = {
            "payout.sent",
            "payout.failed",
            "payout.completed",
            "payout.transferred",
            "payout.canceled",
            "payout.cancelled",
        }
        if event_name in payout_events or (
            event_name.startswith("payout.") and entity.get("id") is not None
        ):
            if isinstance(entity, dict) and "v1/payout" in entity:
                entity = entity["v1/payout"]
            apply_payout_webhook(entity, event_name=event_name)
            return

        if event_name not in {
            "transaction.approved",
            "transaction.transferred",
            "transaction.declined",
            "transaction.canceled",
            "transaction.cancelled",
        }:
            logger.info("Unhandled FedaPay event: %s", event_name)
            return

        tx_id = str(entity.get("id") or "")
        if not tx_id:
            meta = entity.get("custom_metadata") or {}
            # fallback
            pass

        payment = None
        if tx_id:
            payment = Payment.objects.filter(fedapay_transaction_id=str(tx_id)).first()

        if payment is None:
            meta = entity.get("custom_metadata") or {}
            contract_id = meta.get("contract_id")
            if contract_id:
                payment = (
                    Payment.objects.filter(contract_id=contract_id)
                    .order_by("-created_at")
                    .first()
                )

        if payment is None:
            logger.warning("Payment not found for event %s entity=%s", event_name, entity)
            return

        if event_name in {"transaction.approved", "transaction.transferred"}:
            # Re-vérifie auprès de l'API (défense en profondeur)
            try:
                verified = fedapay_service.verify_payment(payment.fedapay_transaction_id)
                if not verified["is_paid"]:
                    logger.warning(
                        "Webhook approved but API status=%s", verified["status"]
                    )
                    return
            except FedaPayError as exc:
                logger.error("verify_payment failed: %s", exc)
                # On fait confiance au webhook signé si verify échoue réseau
            mark_contract_funded(payment, transaction_payload=entity)
        elif event_name in {
            "transaction.declined",
            "transaction.canceled",
            "transaction.cancelled",
        }:
            if payment.status == PaymentStatus.PENDING:
                payment.status = (
                    PaymentStatus.DECLINED
                    if "declined" in event_name
                    else PaymentStatus.CANCELED
                )
                payment.raw_response = {
                    **(payment.raw_response or {}),
                    "webhook_transaction": entity,
                }
                payment.save()


@method_decorator(csrf_exempt, name="dispatch")
class FedaPayCallbackView(APIView):
    """
    Callback navigateur après paiement FedaPay.
    Query typique : ?contract_id=2&status=approved&id=479542
    Doit synchroniser le paiement (le webhook peut échouer / être lent).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        contract_id = request.query_params.get("contract_id")
        status_q = (request.query_params.get("status") or "").lower()
        tx_id = request.query_params.get("id") or request.query_params.get("transaction_id")

        payment = None
        if tx_id:
            payment = Payment.objects.filter(fedapay_transaction_id=str(tx_id)).first()
        if payment is None and contract_id:
            payment = (
                Payment.objects.filter(contract_id=contract_id)
                .order_by("-created_at")
                .first()
            )

        synced = False
        if payment and status_q in {"approved", "transferred"}:
            try:
                mark_contract_funded(
                    payment,
                    transaction_payload={"callback": dict(request.query_params)},
                )
                synced = True
            except Exception:  # noqa: BLE001
                logger.exception("Callback sync failed for payment %s", payment.id)
        elif payment and status_q in {"declined", "canceled", "cancelled"}:
            if payment.status == PaymentStatus.PENDING:
                payment.status = (
                    PaymentStatus.DECLINED
                    if status_q == "declined"
                    else PaymentStatus.CANCELED
                )
                payment.raw_response = {
                    **(payment.raw_response or {}),
                    "callback": dict(request.query_params),
                }
                payment.save(update_fields=["status", "raw_response", "updated_at"])

        # Page HTML minimale pour la WebView (évite un JSON brut)
        title = "Paiement confirmé" if synced or status_q in {"approved", "transferred"} else "Paiement"
        msg = (
            "Paiement confirmé. Vous pouvez revenir à l'application."
            if synced or status_q in {"approved", "transferred"}
            else (
                "Paiement non abouti. Vous pouvez réessayer dans l'application."
                if status_q in {"declined", "canceled", "cancelled"}
                else "Paiement en cours de confirmation. Vous pouvez fermer cette page."
            )
        )
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0b1220;color:#fff;text-align:center;padding:24px}}
.card{{max-width:360px}} h1{{font-size:1.25rem}} p{{opacity:.85}}</style></head>
<body><div class="card"><h1>{title}</h1><p>{msg}</p></div></body></html>"""
        from django.http import HttpResponse

        return HttpResponse(html, content_type="text/html; charset=utf-8")

