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

    class Meta:
        model = JobOffer
        fields = [
            "id",
            "client",
            "title",
            "description",
            "location",
            "price_range_min",
            "price_range_max",
            "service_date",
            "is_recurring",
            "recurrence_frequency",
            "created_at",
            "updated_at",
            "is_filled",
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
            "location",
            "price",
            "completed",
            "created_at",
            "updated_at",
        ]
