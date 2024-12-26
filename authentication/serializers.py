from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

from authentication.models import Review

User = get_user_model()

class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for the Review model.
    """
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_profile_picture = serializers.CharField(source='user.profile_picture', read_only=True)
    user_picture_url = serializers.CharField(source='user.picture_url', read_only=True)
    class Meta:
        model = Review
        fields = ['user_id', 'user_first_name', 'user_last_name', 'user_email', 'user_profile_picture', 'user_picture_url', 'rating', 'testimonials']

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    """
    reviews = ReviewSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = "__all__"

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews:
            return sum(review.rating for review in reviews if review.rating) / len(reviews)
        return None
    
class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for registering a new user.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'password']

class PhoneNumberValidateConfirmSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    otp_code = serializers.CharField(min_length=5, max_length=5)

class CodePINSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['code_PIN']

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
            user = User.objects.get(otp_code=value, is_active=False, verified_email=False)
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP. Please try again.")

class EmailValidateRequestSerializer(serializers.Serializer):
    """
    Serializer for email validation request.
    """
    email = serializers.EmailField()

class LoginSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        email_or_phone = data.get('email_or_phone')
        password = data.get('password')

        if not email_or_phone or not password:
            raise serializers.ValidationError("Both 'email_or_phone' and 'password' are required.")

        user = None
        if '@' in email_or_phone:
            try:
                user = User.objects.get(email=email_or_phone)
                if not user.check_password(password):
                    raise serializers.ValidationError("The password does not match the email.")
            except User.DoesNotExist:
                raise serializers.ValidationError("No account found with this email.")
        else:
            try:
                user = User.objects.get(phone_number=email_or_phone)
                if not user.check_password(password):
                    raise serializers.ValidationError("The password does not match the phone number.")
            except User.DoesNotExist:
                raise serializers.ValidationError("No account found with this phone number.")

        if user is None:
            raise serializers.ValidationError("Invalid login credentials.")

        data['user'] = user
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

class WhatsAppLoginSerializer(serializers.Serializer):
    """
    Serializer for WhatsApp login.
    """
    phone_number = serializers.CharField()
    code_PIN = serializers.CharField(min_length=4, max_length=4, required=False)

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
        user = self.context['request'].user
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
        fields = '__all__'

