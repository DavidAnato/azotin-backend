from django.contrib.auth import get_user_model
from rest_framework import serializers

from decimal import Decimal

from app_escrow.models import (
    Contract,
    Payment,
    Wallet,
    WalletTransaction,
    Withdrawal,
)
from app_escrow.platform_settings import get_platform_settings

User = get_user_model()


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "phone_number", "email", "profile_picture")


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "fedapay_transaction_id",
            "fedapay_reference",
            "amount",
            "currency",
            "status",
            "payment_url",
            "paid_at",
            "created_at",
        )
        read_only_fields = fields


def _absolute_media_url(serializer, file_field):
    if not file_field:
        return None
    try:
        url = file_field.url
    except (ValueError, AttributeError):
        return None
    request = serializer.context.get("request")
    if request is not None:
        return request.build_absolute_uri(url)
    return url


class ContractSerializer(serializers.ModelSerializer):
    client = UserBriefSerializer(read_only=True)
    freelancer = UserBriefSerializer(read_only=True)
    latest_payment = serializers.SerializerMethodField()
    deliverable_audio = serializers.SerializerMethodField()
    deliverable_image = serializers.SerializerMethodField()
    commission_percent = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = (
            "id",
            "client",
            "freelancer",
            "job_offer",
            "job",
            "title",
            "description",
            "amount",
            "platform_fee",
            "freelancer_net",
            "commission_percent",
            "currency",
            "deadline",
            "status",
            "deliverable_note",
            "deliverable_url",
            "deliverable_audio",
            "deliverable_image",
            "revision_note",
            "dispute_reason",
            "funded_at",
            "completed_at",
            "created_at",
            "updated_at",
            "latest_payment",
        )
        read_only_fields = (
            "client",
            "job",
            "status",
            "deliverable_note",
            "deliverable_url",
            "deliverable_audio",
            "deliverable_image",
            "revision_note",
            "dispute_reason",
            "funded_at",
            "completed_at",
            "created_at",
            "updated_at",
            "latest_payment",
        )

    def get_commission_percent(self, obj):
        if obj.platform_fee is not None and obj.amount and Decimal(obj.amount) > 0:
            return str(
                (Decimal(obj.platform_fee) * Decimal("100") / Decimal(obj.amount)).quantize(
                    Decimal("0.01")
                )
            )
        return str(get_platform_settings().commission_percent)

    def get_deliverable_audio(self, obj):
        return _absolute_media_url(self, obj.deliverable_audio)

    def get_deliverable_image(self, obj):
        return _absolute_media_url(self, obj.deliverable_image)

    def get_latest_payment(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        return PaymentSerializer(payment).data if payment else None


class ContractCreateSerializer(serializers.ModelSerializer):
    freelancer_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Contract
        fields = (
            "freelancer_id",
            "job_offer",
            "title",
            "description",
            "amount",
            "currency",
            "deadline",
        )

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Le montant doit être positif.")
        return value

    def validate_freelancer_id(self, value):
        if not User.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Freelance introuvable.")
        return value

    def create(self, validated_data):
        freelancer_id = validated_data.pop("freelancer_id")
        client = self.context["request"].user
        if freelancer_id == client.id:
            raise serializers.ValidationError(
                {"freelancer_id": "Impossible de créer un contrat avec soi-même."}
            )
        return Contract.objects.create(
            client=client,
            freelancer_id=freelancer_id,
            **validated_data,
        )


class SubmitDeliverableSerializer(serializers.Serializer):
    deliverable_note = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    deliverable_url = serializers.URLField(required=False, allow_blank=True, default="")
    deliverable_audio = serializers.FileField(required=False, allow_empty_file=False)
    deliverable_image = serializers.ImageField(required=False)

    def validate(self, attrs):
        note = (attrs.get("deliverable_note") or "").strip()
        audio = attrs.get("deliverable_audio")
        if len(note) < 3 and not audio:
            raise serializers.ValidationError(
                "Ajoute un message texte (3 caractères min.) ou un message vocal."
            )
        attrs["deliverable_note"] = note
        return attrs


class RevisionSerializer(serializers.Serializer):
    note = serializers.CharField(min_length=3)


class DisputeSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3)


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("id", "balance", "currency", "updated_at")


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = (
            "id",
            "type",
            "amount",
            "reason",
            "contract",
            "balance_after",
            "created_at",
        )


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = (
            "id",
            "amount",
            "status",
            "phone_number",
            "method",
            "fedapay_status",
            "note",
            "created_at",
            "processed_at",
        )
        read_only_fields = fields


class WithdrawalCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=0, min_value=Decimal("1")
    )
    phone_number = serializers.CharField(required=False, allow_blank=True, default="")
    # Canal wallet (mobile_money / bank) — pas le mode FedaPay (momo_test).
    method = serializers.CharField(required=False, default="mobile_money")
    code_pin = serializers.CharField(
        required=False, allow_blank=True, min_length=4, max_length=4
    )
