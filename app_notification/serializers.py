from rest_framework import serializers

from .models import NotificationToken, UserNotification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "message", "object", "is_read", "created_at"]
        ref_name = "AppNotificationSerializer"


class NotificationTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationToken
        fields = ["id", "user", "token"]
        read_only_fields = ["user"]
        ref_name = "NotificationTokenSerializer"
    