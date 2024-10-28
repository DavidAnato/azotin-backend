from rest_framework import serializers
from app_profile.models import ClientProfile, PreviousWorkPhoto, WorkerProfile
from authentication.serializers import UserSerializer

class ClientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = ClientProfile
        fields = "__all__"

class PreviousWorkPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreviousWorkPhoto
        fields = "__all__"

class WorkerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    previous_work_photos = PreviousWorkPhotoSerializer(many=True)
    class Meta:
        model = WorkerProfile
        fields = "__all__"
