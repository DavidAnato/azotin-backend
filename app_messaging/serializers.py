from django.contrib.auth import get_user_model
from rest_framework import serializers

from app_job.serializers import JobOfferSerializer

from .models import Conversation, Message, MessageMedia

User = get_user_model()


class ParticipantsSerializer(serializers.ModelSerializer):
    is_worker = serializers.SerializerMethodField()
    online_status = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

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
            "is_worker",
        ]

    def get_is_worker(self, obj):
        return hasattr(obj, "worker_profile") and obj.worker_profile is not None

    def get_online_status(self, obj):
        from .presence import visible_online_for

        return visible_online_for(obj)

    def get_profile_picture(self, obj):
        from .presence import absolute_media_url

        if obj.profile_picture:
            return absolute_media_url(obj.profile_picture, self.context.get("request"))
        return None


class MessageMediaSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    file = serializers.SerializerMethodField()

    class Meta:
        model = MessageMedia
        fields = ["id", "message", "file", "type", "name"]
        read_only_fields = ["message"]

    def get_file(self, obj):
        from .presence import absolute_media_url

        return absolute_media_url(obj.file, self.context.get("request"))

    def get_name(self, obj):
        if not obj.file:
            return ""
        return obj.file.name.split("/")[-1]

    def get_type(self, obj):
        name = self.get_name(obj).lower()
        if name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")):
            ext = name.rsplit(".", 1)[-1]
            return "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        if name.endswith((".mp4", ".mov", ".avi", ".webm", ".m4v")):
            return "video/mp4"
        if name.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac")):
            return "audio/m4a"
        if name.endswith(".pdf"):
            return "application/pdf"
        return "application/octet-stream"


class MessageSerializer(serializers.ModelSerializer):
    job_offer = JobOfferSerializer(read_only=True)
    medias = MessageMediaSerializer(many=True, read_only=True)
    is_edited = serializers.SerializerMethodField()
    is_deleted_for_everyone = serializers.BooleanField(
        source="deleted_for_everyone", read_only=True
    )
    can_delete_for_everyone = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    reply_to = serializers.SerializerMethodField()
    reply_to_id = serializers.IntegerField(
        required=False, allow_null=True, write_only=True
    )

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
            "is_edited",
            "is_deleted_for_everyone",
            "can_delete_for_everyone",
            "can_edit",
            "reply_to",
            "reply_to_id",
        ]
        read_only_fields = ["sender", "timestamp", "status", "edited_at", "read_at"]

    def get_is_edited(self, obj):
        if obj.deleted_for_everyone or not obj.edited_at:
            return False
        # Ignore create-time leftovers (former auto_now on edited_at)
        if obj.timestamp:
            delta = (obj.edited_at - obj.timestamp).total_seconds()
            if delta < 5:
                return False
        return True

    def get_can_delete_for_everyone(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        from .message_visibility import can_delete_for_everyone

        return can_delete_for_everyone(obj, request.user)

    def get_can_edit(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        from .message_visibility import can_edit

        return can_edit(obj, request.user)

    def get_reply_to(self, obj):
        parent = obj.reply_to
        if not parent:
            return None
        sender = parent.sender
        sender_name = (
            f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            or getattr(sender, "username", "")
            or str(sender.id)
        )
        return {
            "id": parent.id,
            "content": None if parent.deleted_for_everyone else parent.content,
            "sender": {
                "id": sender.id,
                "name": sender_name,
            },
            "has_media": parent.medias.exists() and not parent.deleted_for_everyone,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.deleted_for_everyone:
            data["content"] = None
            data["medias"] = []
            data["job_offer"] = None
            data["is_edited"] = False
            data["can_edit"] = False
        return data


class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    participants = ParticipantsSerializer(many=True)
    is_archived = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    marked_unread = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "participants",
            "created_at",
            "last_message",
            "unread_count",
            "is_archived",
            "is_muted",
            "marked_unread",
        ]
        read_only_fields = ["created_at"]

    def _member_state(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return obj.member_states.filter(user=request.user).first()

    def get_is_archived(self, obj):
        state = self._member_state(obj)
        return bool(state and state.archived_at)

    def get_is_muted(self, obj):
        state = self._member_state(obj)
        return bool(state and state.muted)

    def get_marked_unread(self, obj):
        state = self._member_state(obj)
        return bool(state and state.marked_unread)

    def get_last_message(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        if not user or not user.is_authenticated:
            last_message = obj.messages.order_by("-timestamp").first()
        else:
            from .message_visibility import last_visible_message

            last_message = last_visible_message(obj, user)
        if last_message:
            return MessageSerializer(last_message, context=self.context).data
        return None

    def get_unread_count(self, obj):
        user = self.context["request"].user
        from .message_visibility import unread_visible_count

        return unread_visible_count(obj, user)
