"""
Tests Escrow + FedaPay webhook (signature + idempotence + wallet).
"""

import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from app_escrow.models import (
    Contract,
    ContractStatus,
    Payment,
    PaymentStatus,
    Wallet,
    WalletTransaction,
    WalletTransactionType,
    WebhookEventLog,
)
from app_escrow.services.escrow import approve_contract, mark_contract_funded
from app_escrow.services.fedapay import FedaPayService

User = get_user_model()


def _make_user(phone: str, **kwargs):
    return User.objects.create_user(
        phone_number=phone,
        password="testpass123",
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        email=kwargs.get("email", f"{phone}@test.local"),
    )


def _sign(payload: bytes, secret: str) -> str:
    ts = int(time.time())
    signed = f"{ts}.{payload.decode('utf-8')}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},s={sig}"


class FedaPaySignatureTests(TestCase):
    def test_valid_signature(self):
        secret = "wh_sandbox_test"
        payload = b'{"name":"transaction.approved","id":"evt_1"}'
        header = _sign(payload, secret)
        self.assertTrue(
            FedaPayService.verify_webhook_signature(payload, header, secret)
        )

    def test_invalid_signature(self):
        with self.assertRaises(Exception):
            FedaPayService.verify_webhook_signature(
                b"{}", "t=1,s=bad", "wh_sandbox_test"
            )


class ContractFlowTests(APITestCase):
    def setUp(self):
        self.client_user = _make_user("22961000001", first_name="Client")
        self.freelancer = _make_user("22961000002", first_name="Pro")
        self.api = APIClient()

    def test_create_list_accept(self):
        self.api.force_authenticate(self.client_user)
        res = self.api.post(
            "/contracts/",
            {
                "freelancer_id": self.freelancer.id,
                "title": "Réparation plomberie",
                "description": "Fuite cuisine",
                "amount": 15000,
                "currency": "XOF",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        contract_id = res.data["id"]
        self.assertEqual(res.data["status"], ContractStatus.PENDING)

        self.api.force_authenticate(self.freelancer)
        res2 = self.api.post(f"/contracts/{contract_id}/accept/")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["status"], ContractStatus.ACCEPTED)

    @patch("app_escrow.services.escrow.fedapay_service")
    def test_fund_creates_payment(self, mock_feda):
        mock_feda.create_transaction.return_value = {
            "id": 999,
            "reference": "ref_1",
            "status": "pending",
        }
        mock_feda.generate_payment_token.return_value = {
            "token": "tok",
            "url": "https://sandbox-checkout.fedapay.com/pay/tok",
        }

        contract = Contract.objects.create(
            client=self.client_user,
            freelancer=self.freelancer,
            title="Job",
            description="Desc",
            amount=10000,
            status=ContractStatus.ACCEPTED,
        )
        self.api.force_authenticate(self.client_user)
        res = self.api.post(f"/contracts/{contract.id}/fund/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("payment_url", res.data)
        self.assertEqual(res.data["contract"]["status"], ContractStatus.WAITING_PAYMENT)
        self.assertTrue(
            Payment.objects.filter(
                contract=contract, fedapay_transaction_id="999"
            ).exists()
        )


@override_settings(
    FEDAPAY_WEBHOOK_SECRET="wh_sandbox_test",
    FEDAPAY_SKIP_WEBHOOK_SIGNATURE=False,
)
class WebhookTests(APITestCase):
    def setUp(self):
        self.client_user = _make_user("22961000011")
        self.freelancer = _make_user("22961000012")
        self.contract = Contract.objects.create(
            client=self.client_user,
            freelancer=self.freelancer,
            title="Escrow",
            description="Desc",
            amount=20000,
            status=ContractStatus.WAITING_PAYMENT,
        )
        self.payment = Payment.objects.create(
            contract=self.contract,
            fedapay_transaction_id="555",
            amount=20000,
            status=PaymentStatus.PENDING,
        )

    @patch("app_escrow.views.fedapay_service.verify_payment")
    def test_webhook_approved_funds_contract(self, mock_verify):
        mock_verify.return_value = {
            "is_paid": True,
            "status": "approved",
            "transaction": {"id": 555},
        }
        payload = {
            "id": "evt_approved_1",
            "name": "transaction.approved",
            "entity": {"id": 555, "status": "approved", "amount": 20000},
        }
        raw = json.dumps(payload).encode("utf-8")
        header = _sign(raw, "wh_sandbox_test")
        res = self.client.post(
            "/api/payments/fedapay/webhook/",
            data=raw,
            content_type="application/json",
            HTTP_X_FEDAPAY_SIGNATURE=header,
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.contract.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.APPROVED)
        self.assertEqual(self.contract.status, ContractStatus.WORKING)

        # Idempotence
        res2 = self.client.post(
            "/api/payments/fedapay/webhook/",
            data=raw,
            content_type="application/json",
            HTTP_X_FEDAPAY_SIGNATURE=header,
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json().get("duplicate"))
        self.assertEqual(WebhookEventLog.objects.filter(event_id="evt_approved_1").count(), 1)


class WalletTests(APITestCase):
    def setUp(self):
        self.client_user = _make_user("22961000021")
        self.freelancer = _make_user("22961000022")
        self.contract = Contract.objects.create(
            client=self.client_user,
            freelancer=self.freelancer,
            title="Done",
            description="Desc",
            amount=5000,
            status=ContractStatus.SUBMITTED,
        )
        self.api = APIClient()

    def test_approve_credits_wallet(self):
        approve_contract(self.contract, self.client_user)
        wallet = Wallet.objects.get(owner=self.freelancer)
        self.assertEqual(wallet.balance, Decimal("4500"))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.platform_fee, Decimal("500"))
        self.assertEqual(self.contract.freelancer_net, Decimal("4500"))
        self.assertTrue(
            WalletTransaction.objects.filter(
                wallet=wallet,
                type=WalletTransactionType.ESCROW_RELEASE,
                contract=self.contract,
                amount=Decimal("4500"),
            ).exists()
        )
        # Double approve ne double pas le crédit
        self.contract.status = ContractStatus.SUBMITTED
        self.contract.save(update_fields=["status"])
        # transition invalid — skip

    def test_withdraw(self):
        wallet, _ = Wallet.objects.get_or_create(owner=self.freelancer)
        wallet.balance = Decimal("8000")
        wallet.save()
        self.api.force_authenticate(self.freelancer)
        with patch("app_escrow.services.escrow.fedapay_service") as mock_feda:
            mock_feda.create_payout.return_value = {"id": 42, "status": "pending"}
            mock_feda.start_payouts.return_value = {"started": True}
            res = self.api.post(
                "/wallet/withdraw/",
                {"amount": 3000, "phone_number": "22961000022"},
                format="json",
            )
        self.assertEqual(res.status_code, 201, res.data)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("5000"))
        self.assertEqual(res.data["status"], "processing")
        mock_feda.create_payout.assert_called_once()
        mock_feda.start_payouts.assert_called_once_with([42])
