from django.contrib.auth import get_user_model
from rest_framework import serializers

from app_job.serializers import JobOfferSerializer

from .models import Conversation, Message, MessageMedia

User = get_user_model()


class ParticipantsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "profile_picture",
            "picture_url",
            "username",
            "online_status",
        ]


class MessageMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageMedia
        fields = ["id", "message", "file"]
        read_only_fields = ["message"]


class MessageSerializer(serializers.ModelSerializer):
    job_offer = JobOfferSerializer(read_only=True)
    medias = MessageMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "content",
            "medias",
            "job_offer",
            "timestamp",
            "status",
            "edited_at",
            "read_at",
        ]
        read_only_fields = ["sender", "timestamp", "status", "edited_at", "read_at"]


class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    participants = ParticipantsSerializer(many=True)

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
