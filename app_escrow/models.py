"""
Modèles Escrow AZOTIN — contrats sous séquestre + portefeuille.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ContractStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    PENDING = "PENDING", "En attente d'acceptation"
    ACCEPTED = "ACCEPTED", "Accepté"
    WAITING_PAYMENT = "WAITING_PAYMENT", "En attente de paiement"
    FUNDED = "FUNDED", "Fonds bloqués (séquestre)"
    WORKING = "WORKING", "En cours"
    SUBMITTED = "SUBMITTED", "Livrable soumis"
    REVISION = "REVISION", "Révisions demandées"
    COMPLETED = "COMPLETED", "Terminé"
    DISPUTE = "DISPUTE", "Litige"
    CANCELLED = "CANCELLED", "Annulé"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    APPROVED = "approved", "Approuvé"
    DECLINED = "declined", "Refusé"
    CANCELED = "canceled", "Annulé"
    TRANSFERRED = "transferred", "Transféré"


class WalletTransactionType(models.TextChoices):
    CREDIT = "credit", "Crédit"
    DEBIT = "debit", "Débit"
    ESCROW_RELEASE = "escrow_release", "Libération séquestre"
    WITHDRAWAL = "withdrawal", "Retrait"
    REFUND = "refund", "Remboursement"
    PLATFORM_FEE = "platform_fee", "Commission plateforme"


class PlatformSettings(models.Model):
    """Singleton — commission prélevée à la libération du séquestre."""

    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres plateforme"
        verbose_name_plural = "Paramètres plateforme"

    def __str__(self):
        return f"Commission {self.commission_percent}%"


class WithdrawalStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En cours"
    COMPLETED = "completed", "Terminé"
    FAILED = "failed", "Échoué"
    CANCELLED = "cancelled", "Annulé"


class Contract(models.Model):
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contracts_as_client",
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contracts_as_freelancer",
    )
    job_offer = models.ForeignKey(
        "app_job.JobOffer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrow_contracts",
    )
    job = models.OneToOneField(
        "app_job.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrow_contract",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    platform_fee = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True
    )
    freelancer_net = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="XOF")
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=ContractStatus.choices,
        default=ContractStatus.PENDING,
        db_index=True,
    )
    deliverable_note = models.TextField(blank=True, default="")
    deliverable_url = models.URLField(blank=True, default="")
    deliverable_audio = models.FileField(
        upload_to="escrow/deliverables/audio/",
        null=True,
        blank=True,
    )
    deliverable_image = models.ImageField(
        upload_to="escrow/deliverables/images/",
        null=True,
        blank=True,
    )
    revision_note = models.TextField(blank=True, default="")
    dispute_reason = models.TextField(blank=True, default="")
    funded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["freelancer", "status"]),
        ]

    def __str__(self):
        return f"Contract#{self.pk} {self.title} [{self.status}]"

    def clean(self):
        if self.client_id and self.freelancer_id and self.client_id == self.freelancer_id:
            raise ValidationError("Le client et le freelance doivent être distincts.")
        if self.amount is not None and self.amount <= 0:
            raise ValidationError("Le montant doit être strictement positif.")


class Payment(models.Model):
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    fedapay_transaction_id = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )
    fedapay_reference = models.CharField(max_length=128, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(
        max_length=32,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    payment_url = models.URLField(max_length=1024, blank=True, default="")
    payment_token = models.CharField(max_length=512, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment#{self.pk} tx={self.fedapay_transaction_id} [{self.status}]"


class Wallet(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(
        max_digits=14, decimal_places=0, default=Decimal("0")
    )
    currency = models.CharField(max_length=3, default="XOF")
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wallet#{self.pk} user={self.owner_id} bal={self.balance}"


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    type = models.CharField(max_length=32, choices=WalletTransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    reason = models.CharField(max_length=255)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions",
    )
    balance_after = models.DecimalField(max_digits=14, decimal_places=0, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Withdrawal(models.Model):
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="withdrawals",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    status = models.CharField(
        max_length=32,
        choices=WithdrawalStatus.choices,
        default=WithdrawalStatus.PENDING,
    )
    phone_number = models.CharField(max_length=32, blank=True, default="")
    method = models.CharField(max_length=64, blank=True, default="mobile_money")
    fedapay_payout_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    fedapay_status = models.CharField(max_length=32, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    note = models.TextField(blank=True, default="")
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class WebhookEventLog(models.Model):
    """Idempotence webhook FedaPay — stocke event.id déjà traités."""

    event_id = models.CharField(max_length=128, unique=True)
    event_name = models.CharField(max_length=128, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-processed_at"]
