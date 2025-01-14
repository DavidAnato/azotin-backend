from rest_framework import serializers

from app_job.models import Category, SubCategory
from app_profile.serializers import ClientProfileSerializer, WorkerProfileSerializer

from .models import Job, JobApplication, JobOffer


# Category Serializer
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


# SubCategory Serializer
class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ["id", "name", "description"]


# JobOffer Serializer
class JobOfferSerializer(serializers.ModelSerializer):
    client = ClientProfileSerializer(read_only=True)
    is_filled = serializers.BooleanField(read_only=True)
    category = CategorySerializer(read_only=True)
    sub_category = SubCategorySerializer(read_only=True)

    class Meta:
        model = JobOffer
        fields = [
            "id",
            "category",
            "sub_category",
            "client",
            "title",
            "image",
            "description",
            "responsability",
            "location",
            "price",
            "service_date",
            "is_recurring",
            "type",
            "created_at",
            "updated_at",
            "is_filled",
            "location_latitude",
            "location_longitude",
        ]


# JobApplication Serializer
class JobApplicationSerializer(serializers.ModelSerializer):
    worker = WorkerProfileSerializer(read_only=True)
    job_offer = JobOfferSerializer(read_only=True)
    status = serializers.CharField(
        read_only=True
    )  # Managed by the server, cannot be set by the user directly

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "job_offer",
            "worker",
            "proposed_price",
            "cover_letter",
            "status",
            "applied_at",
        ]


# Job Serializer
class JobSerializer(serializers.ModelSerializer):
    client = ClientProfileSerializer(read_only=True)
    worker = WorkerProfileSerializer(read_only=True)
    job_offer = JobOfferSerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "job_offer",
            "client",
            "worker",
            "description",
            "price",
            "completed",
            "created_at",
            "updated_at",
        ]
