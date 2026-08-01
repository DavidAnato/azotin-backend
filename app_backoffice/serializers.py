from django.contrib.auth import get_user_model
from rest_framework import serializers

from app_escrow.models import PlatformSettings, Wallet, Withdrawal
from app_escrow.serializers import ContractSerializer, UserBriefSerializer

from .models import BackofficeNotification, ContentReport

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


class BackofficeNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackofficeNotification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "object_id",
            "created_at",
            "users_read",
        ]
        ref_name = "BackofficeNotificationSerializer"


class JobStatisticsSerializer(serializers.Serializer):
    job_offer_count = serializers.IntegerField()
    job_application_count = serializers.IntegerField()
    job_progress_count = serializers.IntegerField()
    job_completed_count = serializers.IntegerField()


class ContentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentReport
        fields = [
            "id",
            "target_type",
            "target_id",
            "reason",
            "details",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]


class StaffContractSerializer(ContractSerializer):
    """Read-only contract payload for staff backoffice lists/details."""

    payments_count = serializers.SerializerMethodField()

    class Meta(ContractSerializer.Meta):
        fields = ContractSerializer.Meta.fields + ("payments_count",)
        read_only_fields = fields

    def get_payments_count(self, obj):
        return obj.payments.count()


class StaffWalletSerializer(serializers.ModelSerializer):
    owner = UserBriefSerializer(read_only=True)
    withdrawals_count = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = (
            "id",
            "owner",
            "balance",
            "currency",
            "withdrawals_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_withdrawals_count(self, obj):
        return obj.withdrawals.count()


class StaffWithdrawalSerializer(serializers.ModelSerializer):
    wallet_id = serializers.IntegerField(source="wallet.id", read_only=True)
    owner = UserBriefSerializer(source="wallet.owner", read_only=True)
    wallet_balance = serializers.DecimalField(
        source="wallet.balance",
        max_digits=14,
        decimal_places=0,
        read_only=True,
    )
    currency = serializers.CharField(source="wallet.currency", read_only=True)

    class Meta:
        model = Withdrawal
        fields = (
            "id",
            "wallet_id",
            "owner",
            "wallet_balance",
            "amount",
            "currency",
            "status",
            "phone_number",
            "method",
            "note",
            "created_at",
        )
        read_only_fields = fields


class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSettings
        fields = ("commission_percent", "updated_at")
        read_only_fields = ("updated_at",)

