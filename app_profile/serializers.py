from rest_framework import serializers

from app_profile.models import ClientProfile, PreviousWorkPhoto, WorkerProfile
from authentication.serializers import UserSerializer
from app_job.models import Category, SubCategory

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


# SubCategory Serializer
class TitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ["id", "name", "description"]


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
    category = CategorySerializer()
    title = TitleSerializer()

    class Meta:
        model = WorkerProfile
        fields = "__all__"
