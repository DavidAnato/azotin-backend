from django.contrib import admin

from .models import BackofficeNotification, ContentReport


@admin.register(BackofficeNotification)
class BackofficeNotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "notification_type", "object_id", "created_at")
    list_filter = ("notification_type", "created_at")
    search_fields = ("title", "message", "object_id")
    filter_horizontal = ("users_read",)
    readonly_fields = ("created_at",)


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "target_type",
        "target_id",
        "reason",
        "status",
        "created_at",
    )
    list_filter = ("status", "target_type", "reason", "created_at")
    search_fields = (
        "details",
        "reporter__first_name",
        "reporter__last_name",
        "reporter__phone_number",
    )
    raw_id_fields = ("reporter",)
    readonly_fields = ("created_at",)
    list_editable = ("status",)
