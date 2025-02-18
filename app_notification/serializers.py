from rest_framework import serializers

from .models import UserNotification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = ["id", "message", "object", "is_read", "created_at"]
        ref_name = "AppNotificationSerializer"
