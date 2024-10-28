from django.contrib.auth import get_user_model
from .models import Notification
from rest_framework import serializers

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"

class JobStatisticsSerializer(serializers.Serializer):
    job_offer_count = serializers.IntegerField()
    job_application_count = serializers.IntegerField()
    job_progress_count = serializers.IntegerField()
    job_completed_count = serializers.IntegerField()

