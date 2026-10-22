from rest_framework import serializers

from app_job.models import Category, SubCategory
from app_profile.models import ClientProfile, PreviousWorkPhoto, WorkerProfile
from authentication.serializers import UserSerializer
from azobatin_api.ai_sanitize import sanitize_ai_text


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]
        ref_name = "ProfileCategorySerializer"


# SubCategory Serializer
class TitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ["id", "name", "description"]


def parse_job_type_ids(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            parts.extend(str(item).split(","))
    else:
        parts = str(raw).split(",")
    ids = []
    for part in parts:
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def apply_job_types(worker_profile, ids):
    if ids is None:
        return
    valid = set(SubCategory.objects.filter(id__in=ids).values_list("id", flat=True))
    ordered = []
    seen = set()
    for pk in ids:
        if pk in valid and pk not in seen:
            ordered.append(pk)
            seen.add(pk)
    worker_profile.job_types.set(ordered)
    if ordered:
        if worker_profile.title_id not in seen:
            worker_profile.title_id = ordered[0]
            worker_profile.save()
    elif worker_profile.title_id:
        worker_profile.job_types.add(worker_profile.title_id)


class JobTypesPKField(serializers.Field):
    """Accepte une liste d'ids, un id, ou une chaîne '1,2,3' (multipart)."""

    def get_value(self, dictionary):
        if hasattr(dictionary, "getlist"):
            values = dictionary.getlist(self.field_name)
            if len(values) > 1:
                return values
            if len(values) == 1:
                return values[0]
            return serializers.empty
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        ids = parse_job_type_ids(data)
        return ids if ids is not None else []

    def to_representation(self, value):
        if hasattr(value, "all"):
            return list(value.values_list("id", flat=True))
        return value


class ClientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = ClientProfile
        fields = "__all__"

    def validate_service_description(self, value):
        return sanitize_ai_text(value) if isinstance(value, str) else value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(data.get("service_description"), str):
            data["service_description"] = sanitize_ai_text(data["service_description"])
        return data


class PreviousWorkPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreviousWorkPhoto
        fields = "__all__"


class WorkerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    previous_work_photos = PreviousWorkPhotoSerializer(many=True)
    category = CategorySerializer()
    title = TitleSerializer()
    job_types = TitleSerializer(many=True, read_only=True)
    is_favorite = serializers.BooleanField(read_only=True)

    class Meta:
        model = WorkerProfile
        fields = "__all__"


class WorkerProfileSerializerForUpdate(serializers.ModelSerializer):
    user = UserSerializer()
    previous_work_photos = PreviousWorkPhotoSerializer(many=True)
    job_types = JobTypesPKField(required=False)

    class Meta:
        model = WorkerProfile
        fields = "__all__"

    def update(self, instance, validated_data):
        job_type_ids = validated_data.pop("job_types", None)
        instance = super().update(instance, validated_data)
        if job_type_ids is not None:
            apply_job_types(instance, job_type_ids)
        elif instance.title_id:
            instance.job_types.add(instance.title_id)
        return instance
