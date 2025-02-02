from django.contrib import admin

from .models import Conversation, Message, MessageMedia


class MessageMediaInline(admin.TabularInline):
    model = MessageMedia
    extra = 1


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at")
    filter_horizontal = ("participants",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "conversation", "content", "jobOffer", "timestamp", "status", "edited_at", "read_at")
    list_filter = ("status", "timestamp", "edited_at", "read_at")
    search_fields = ("content",)
    inlines = [MessageMediaInline]
