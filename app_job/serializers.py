from rest_framework import serializers

from app_profile.serializers import ClientProfileSerializer, WorkerProfileSerializer

from .models import Category, Job, JobApplication, JobOffer, PaidService, SubCategory


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
            "voice_note",
            "description",
            "responsability",
            "location",
            "price",
            "frequency",
            "service_date",
            "deadline",
            "is_urgent",
            "is_recurring",
            "type",
            "created_at",
            "updated_at",
            "is_filled",
            "location_latitude",
            "location_longitude",
        ]
        extra_kwargs = {
            "sub_category": {"write_only": True},
            "description": {"required": False, "allow_blank": True},
            "responsability": {"required": False, "allow_blank": True},
            "voice_note": {"required": False},
            "location_latitude": {"required": False},
            "location_longitude": {"required": False},
            "deadline": {"required": False, "allow_null": True},
            "is_urgent": {"required": False},
        }

    def validate_sub_category(self, value):
        if isinstance(value, int):
            try:
                return SubCategory.objects.get(id=value)
            except SubCategory.DoesNotExist:
                raise serializers.ValidationError("Sous-catégorie invalide")
        return value


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
            "frequency",
            "cover_letter",
            "voice_note",
            "status",
            "applied_at",
        ]
        extra_kwargs = {
            "cover_letter": {"required": False, "allow_blank": True},
            "voice_note": {"required": False},
            "frequency": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        cover = (attrs.get("cover_letter") or "").strip()
        voice = attrs.get("voice_note")
        # En update partiel, ne pas forcer
        if self.instance is None and not cover and not voice:
            raise serializers.ValidationError(
                {
                    "cover_letter": "Ajoute un message texte ou une note vocale.",
                }
            )
        return attrs


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
            "frequency",
            "completed",
            "created_at",
            "updated_at",
        ]


class PaidServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaidService
        fields = [
            "is_job_offer_paid",
            "is_job_offer_paid_price",
            "is_job_application_paid",
            "is_job_application_paid_price",
        ]
