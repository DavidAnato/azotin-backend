from django.contrib import admin

from app_escrow.models import (
    Contract,
    Payment,
    PlatformSettings,
    Wallet,
    WalletTransaction,
    WebhookEventLog,
    Withdrawal,
)


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "commission_percent", "updated_at")
    readonly_fields = ("updated_at",)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "client", "freelancer", "amount", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("title", "client__phone_number", "freelancer__phone_number")
    raw_id_fields = ("client", "freelancer")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "contract",
        "fedapay_transaction_id",
        "amount",
        "status",
        "paid_at",
    )
    list_filter = ("status",)
    raw_id_fields = ("contract",)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "balance", "currency", "updated_at")
    search_fields = ("owner__phone_number", "owner__first_name", "owner__last_name")
    raw_id_fields = ("owner",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "type", "amount", "reason", "created_at")
    list_filter = ("type",)
    raw_id_fields = ("wallet",)


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "amount", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("wallet",)


@admin.register(WebhookEventLog)
class WebhookEventLogAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_name", "success", "processed_at")
    list_filter = ("success", "event_name")
    search_fields = ("event_id", "event_name")
