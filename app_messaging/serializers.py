from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "sender", "content", "timestamp", "status"]
        read_only_fields = ["sender", "timestamp", "status"]


class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "participants", "created_at", "last_message", "unread_count"]
        read_only_fields = ["created_at"]

    def get_last_message(self, obj):
        last_message = obj.messages.order_by("-timestamp").first()
        if last_message:
            return MessageSerializer(last_message).data
        return None

    def get_unread_count(self, obj):
        user = self.context["request"].user
        return (
            obj.messages.filter(status__in=["sent", "received"])
            .exclude(sender=user)
            .count()
        )
