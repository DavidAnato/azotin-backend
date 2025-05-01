from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import BackofficeNotification

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


class BackofficeNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackofficeNotification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "object_id",
            "created_at",
            "users_read",
        ]
        ref_name = "BackofficeNotificationSerializer"


class JobStatisticsSerializer(serializers.Serializer):
    job_offer_count = serializers.IntegerField()
    job_application_count = serializers.IntegerField()
    job_progress_count = serializers.IntegerField()
    job_completed_count = serializers.IntegerField()
