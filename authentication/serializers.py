from django.contrib.auth import get_user_model
from rest_framework import serializers

from authentication.models import Review, UserSettings
from authentication.otp_service import DEFAULT_OTP_CHANNEL, OTP_CHANNELS
from jobhub_api.ai_sanitize import sanitize_ai_text

User = get_user_model()


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for the Review model.
    """

    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_first_name = serializers.CharField(source="user.first_name", read_only=True)
    user_last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_profile_picture = serializers.CharField(
        source="user.profile_picture", read_only=True
    )
    user_picture_url = serializers.CharField(source="user.picture_url", read_only=True)

    class Meta:
        model = Review
        fields = [
            "user_id",
            "user_first_name",
            "user_last_name",
            "user_email",
            "user_profile_picture",
            "user_picture_url",
            "rating",
            "testimonials",
        ]


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    """

    reviews = ReviewSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = "__all__"

    def validate_bio(self, value):
        return sanitize_ai_text(value) if isinstance(value, str) else value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(data.get("bio"), str):
            data["bio"] = sanitize_ai_text(data["bio"])
        return data

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews if review.rating) / len(
                reviews
            )
        return None

    def get_profile_picture(self, obj):
        if not obj.profile_picture:
            return None
        try:
            url = obj.profile_picture.url
        except (ValueError, AttributeError):
            return None
        from django.conf import settings

        base = (getattr(settings, "PUBLIC_API_BASE_URL", None) or "").rstrip("/")
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if base:
            if not url.startswith("/"):
                url = f"/{url}"
            return f"{base}{url}"
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class OtpChannelField(serializers.ChoiceField):
    """Canal OTP GetOurVoice : sms uniquement (whatsapp ignoré, défaut sms)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("choices", [(c, c) for c in OTP_CHANNELS])
        kwargs.setdefault("required", False)
        kwargs.setdefault("default", DEFAULT_OTP_CHANNEL)
        kwargs.setdefault("write_only", True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if data in (None, ""):
            return DEFAULT_OTP_CHANNEL
        if isinstance(data, str):
            data = data.strip().lower()
        if data == "whatsapp":
            return DEFAULT_OTP_CHANNEL
        return super().to_internal_value(data)


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for registering a new user.
    """

    profile_type = serializers.ChoiceField(
        choices=[("worker", "Travailleur"), ("employer", "Client")],
        write_only=True,
    )
    channel = OtpChannelField()

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "profile_type",
            "channel",
        ]

    def create(self, validated_data):
        validated_data.pop("channel", None)
        profile_type = validated_data.pop("profile_type", None)
        user = User.objects.create(**validated_data)
        if profile_type:
            user.profile_type = profile_type
            user.save(update_fields=["profile_type"])
        return user


class PhoneNumberValidateRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    channel = OtpChannelField()


class PhoneNumberValidateConfirmSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp_code = serializers.CharField(min_length=5, max_length=5)


class CodePINSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["code_pin"]


class OTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for OTP verification.
    """

    otp_code = serializers.CharField(min_length=5, max_length=5)
    email = serializers.EmailField()

    def validate_otp(self, value):
        """
        Validate the OTP code.
        """
        try:
            user = User.objects.get(
                otp_code=value, is_active=False, verified_email=False
            )
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP. Please try again.")


class EmailValidateRequestSerializer(serializers.Serializer):
    """
    Serializer for email validation request.
    """

    email = serializers.EmailField(required=False, allow_blank=True)


class LoginSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        email_or_phone = data.get("email_or_phone")
        password = data.get("password")

        if not email_or_phone or not password:
            raise serializers.ValidationError(
                "Both 'email_or_phone' and 'password' are required."
            )

        user = None
        if "@" in email_or_phone:
            try:
                user = User.objects.get(email=email_or_phone)
                if not user.check_password(password):
                    raise serializers.ValidationError(
                        "The password does not match the email."
                    )
            except User.DoesNotExist:
                raise serializers.ValidationError("No account found with this email.")
        else:
            try:
                user = User.objects.get(phone_number=email_or_phone)
                if not user.check_password(password):
                    raise serializers.ValidationError(
                        "The password does not match the phone number."
                    )
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "No account found with this phone number."
                )

        if user is None:
            raise serializers.ValidationError("Invalid login credentials.")

        data["user"] = user
        return data


class GoogleLoginSerializer(serializers.Serializer):
    """
    Serializer for Google login.
    """

    code = serializers.CharField()

    def validate_code(self, value):
        """
        Validate the authorization code.
        """
        if not value:
            raise serializers.ValidationError("Authorization code is required.")
        return value


class PINLoginSerializer(serializers.Serializer):
    """
    Serializer for PIN login.
    """

    phone_number = serializers.CharField()
    code_pin = serializers.CharField(min_length=4, max_length=4, required=False)


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing the password.
    """

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        """
        Validate the old password.
        """
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct")
        return value

    def validate_new_password(self, value):
        """
        Validate the new password.
        """
        # Add any additional password validations here
        return value


class SetPasswordSerializer(serializers.Serializer):
    """
    Serializer for setting a new password.
    """

    new_password = serializers.CharField(required=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    """

    email_or_phone = serializers.CharField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming the password reset.
    """

    new_password = serializers.CharField(min_length=6, write_only=True)
    otp_code = serializers.CharField(min_length=5, max_length=5)


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile.
    """

    class Meta:
        model = User
        fields = "__all__"


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            "use_biometric",
            "use_face_id",
            "use_pin",
            "notification_email",
            "notification_sms",
            "notification_push",
            "profile_visibility",
            "show_phone_number",
            "show_online_status",
            "allow_messages",
            "allow_calls",
            "sound_enabled",
            "haptics_enabled",
            "marketing_notifications",
            "language",
        ]
        read_only_fields = ["user"]


class DeleteAccountSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=False, allow_blank=True)
    refresh = serializers.CharField(required=False, allow_blank=True)


class KYCSerializer(serializers.Serializer):
    id_type = serializers.CharField(required=False, allow_blank=True, default="")
    id_number = serializers.CharField(required=False, allow_blank=True, default="")
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    id_document = serializers.ImageField(required=False, allow_null=True)
    piece = serializers.ImageField(required=False, allow_null=True)
    selfie = serializers.ImageField(required=False, allow_null=True)
    kyc_status = serializers.CharField(read_only=True)
    kyc_submitted_at = serializers.DateTimeField(read_only=True)
    is_certified = serializers.BooleanField(read_only=True)
