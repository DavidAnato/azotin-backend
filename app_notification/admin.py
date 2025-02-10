from django.contrib import admin

from .models import UserNotification


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "message", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("message", "recipient__email")
    readonly_fields = ("created_at",)
