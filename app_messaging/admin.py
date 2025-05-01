from django.contrib import admin

from .models import Conversation, Message, MessageMedia


class MessageMediaInline(admin.TabularInline):
    model = MessageMedia
    extra = 1


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "updated_at",
    )
    filter_horizontal = ("participants",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "conversation",
        "sender",
        "content",
        "status",
        "timestamp",
        "job_offer",
        "edited_at",
        "read_at",
    )
    list_filter = ("status", "timestamp", "edited_at", "read_at")
    search_fields = ("content", "sender__first_name", "sender__last_name")
    inlines = [MessageMediaInline]


@admin.register(MessageMedia)
class MessageMediaAdmin(admin.ModelAdmin):
    list_display = ("message", "file")
