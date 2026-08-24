from django.contrib import admin

from .models import NotificationToken, UserNotification


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "short_message", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = (
        "message",
        "recipient__email",
        "recipient__phone_number",
        "recipient__first_name",
        "recipient__last_name",
    )
    readonly_fields = ("created_at",)
    raw_id_fields = ("recipient",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="Message")
    def short_message(self, obj):
        text = obj.message or ""
        return text if len(text) <= 80 else f"{text[:77]}..."


@admin.register(NotificationToken)
class NotificationTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "token_preview")
    search_fields = (
        "token",
        "user__email",
        "user__phone_number",
        "user__first_name",
        "user__last_name",
    )
    raw_id_fields = ("user",)
    ordering = ("-id",)

    @admin.display(description="Token")
    def token_preview(self, obj):
        token = obj.token or ""
        if len(token) <= 48:
            return token
        return f"{token[:24]}…{token[-12:]}"
