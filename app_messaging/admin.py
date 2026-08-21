from django.contrib import admin

from .models import Conversation, ConversationMemberState, Message, MessageMedia


class MessageMediaInline(admin.TabularInline):
    model = MessageMedia
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "updated_at",
    )
    filter_horizontal = ("participants",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ConversationMemberState)
class ConversationMemberStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "user",
        "muted",
        "marked_unread",
        "hidden_at",
        "archived_at",
        "updated_at",
    )
    list_filter = ("muted", "marked_unread")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__phone_number",
    )
    raw_id_fields = ("conversation", "user")
    readonly_fields = ("updated_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "sender",
        "content",
        "status",
        "timestamp",
        "job_offer",
        "deleted_for_everyone",
    )
    list_filter = ("status", "deleted_for_everyone", "timestamp")
    search_fields = ("content", "sender__first_name", "sender__last_name")
    raw_id_fields = ("conversation", "sender", "job_offer", "reply_to")
    filter_horizontal = ("hidden_for",)
    inlines = [MessageMediaInline]


@admin.register(MessageMedia)
class MessageMediaAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "file", "created_at")
    raw_id_fields = ("message",)
    readonly_fields = ("created_at",)
