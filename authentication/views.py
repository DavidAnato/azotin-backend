# Third-party imports
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from app_profile.models import ClientProfile, WorkerProfile
from app_profile.serializers import (
    ClientProfileSerializer,
    PreviousWorkPhotoSerializer,
    WorkerProfileSerializer,
)

from .otp_service import send_otp, verify_otp
from .serializers import (
    ChangePasswordSerializer,
    CodePINSerializer,
    EmailValidateRequestSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    OTPVerificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneNumberValidateConfirmSerializer,
    PhoneNumberValidateRequestSerializer,
    PINLoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
)

# Local imports
from .utils import (
    send_activation_email,
    send_password_reset_email,
    send_whatsapp_message,
)

User = get_user_model()


class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Vérifier que les clés API sont configurées
            if not settings.OURVOICE_API_KEY or not settings.OURVOICE_APP_ID:
                return Response(
                    {"error": "La configuration GetOurVoice est manquante."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # On essaie d'abord d'envoyer l'OTP si un numéro de téléphone est fourni
            phone_number = serializer.validated_data.get("phone_number")
            if phone_number:
                # Envoyer un OTP via GetOurVoice
                success, response = send_otp(
                    phone_number=phone_number,
                    api_key=settings.OURVOICE_API_KEY,
                    app_id=settings.OURVOICE_APP_ID,
                )

                if not success:
                    return Response(
                        {
                            "error": response.get(
                                "error", "Échec de l'envoi du code OTP."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Si l'envoi OTP a réussi, créer l'utilisateur
                user = serializer.save()
                user.is_active = False
                user.save()

                # Créer le profil en fonction du type de profil
                profile_type = serializer.validated_data.get("profile_type")
                if profile_type == "worker":
                    WorkerProfile.objects.create(user=user)
                elif profile_type == "employer":
                    ClientProfile.objects.create(user=user)

                return Response(
                    {"message": "Code OTP envoyé avec succès."},
                    status=status.HTTP_201_CREATED,
                )
            else:
                # Si pas de numéro de téléphone, créer l'utilisateur directement
                user = serializer.save()
                return Response(
                    {"message": "Compte créé avec succès."},
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {"error": f"Erreur lors de l'inscription: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PhoneNumberValidateRequestView(generics.CreateAPIView):
    serializer_class = PhoneNumberValidateRequestSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]

        try:
            # Vérifier si l'utilisateur existe
            User.objects.get(phone_number=phone_number)

            # Envoyer l'OTP via GetOurVoice
            success, response = send_otp(
                phone_number=phone_number,
                api_key=settings.OURVOICE_API_KEY,
                app_id=settings.OURVOICE_APP_ID,
            )

            # Vérifier si l'envoi a réussi
            if not success:
                return Response(
                    {"error": response.get("error", "Échec de l'envoi du code OTP.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"message": "Code OTP envoyé avec succès."},
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Utilisateur non trouvé avec ce numéro."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Erreur lors de l'envoi du code OTP: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PhoneNumberValidateConfirmView(generics.CreateAPIView):
    serializer_class = PhoneNumberValidateConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        otp_code = serializer.validated_data["otp_code"]

        try:
            user = User.objects.get(phone_number=phone_number)

            # Vérifier l'OTP via GetOurVoice
            success, response = verify_otp(
                phone_number=phone_number,
                code=otp_code,
                api_key=settings.OURVOICE_API_KEY,
                app_id=settings.OURVOICE_APP_ID,
            )

            if not success:
                error_message = response.get("error") or response.get(
                    "message", "Code OTP invalide."
                )
                return Response(
                    {"error": error_message},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.is_active = True
            user.save()
            return Response(
                {
                    "message": "Numéro de téléphone validé avec succès.",
                    "details": response.get("message", ""),
                },
                status=status.HTTP_200_OK,
            )
        except User.DoesNotExist:
            return Response(
                {"error": "Utilisateur non trouvé avec ce numéro."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Erreur lors de la vérification du code OTP: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class EmailValidateRequestView(generics.CreateAPIView):
    serializer_class = EmailValidateRequestSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
            if user.is_active:
                return Response(
                    {"error": "User with this email is already activated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except User.DoesNotExist:
            return Response(
                {"error": "User with this email not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate new OTP
        otp_code = get_random_string(length=5, allowed_chars="1234567890")
        user.otp_code = otp_code
        user.otp_generated_at = timezone.now()
        user.save()

        # Send email with new OTP
        activation_link = (
            self.request.build_absolute_uri(reverse("activate-email"))
            + f"?otp_code={otp_code}&email={user.email}"
        )
        send_activation_email(user.email, otp_code, activation_link)

        return Response(
            {"message": "New OTP sent successfully."}, status=status.HTTP_201_CREATED
        )


class EmailActivateView(generics.GenericAPIView):
    serializer_class = OTPVerificationSerializer

    def get(self, request, *args, **kwargs):
        otp_code = request.query_params.get("otp_code")
        email = request.query_params.get("email")

        if not otp_code or not email:
            return Response(
                {"error": "OTP and email are required in query parameters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activation_response = self.activate_account(email, otp_code)
        if activation_response.status_code == status.HTTP_200_OK:
            return redirect("http://localhost:3000/activation-success")
        else:
            return activation_response

    def post(self, request, *args, **kwargs):
        return self.activate_account(
            request.data.get("email"), request.data.get("otp_code")
        )

    def activate_account(self, email, otp_code):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST
            )
        if user.otp_code != otp_code:
            return Response(
                {"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST
            )

        if (
            user.otp_generated_at
            and user.otp_generated_at + timezone.timedelta(hours=3) < timezone.now()
        ):
            return Response(
                {"error": "OTP has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.verified_email = True
        user.save()

        return Response(
            {"message": "Your account has been activated successfully."},
            status=status.HTTP_200_OK,
        )


class BaseLoginView(APIView):
    """
    Base class for login views to enrich user data with profile-specific information.
    """

    def enrich_user_data(self, user):
        user_data = UserSerializer(user).data

        try:
            if hasattr(user, "worker_profile"):
                worker_profile = WorkerProfileSerializer(user.worker_profile).data
                worker_profile["previous_work_photos"] = PreviousWorkPhotoSerializer(
                    user.worker_profile.previous_work_photos.all(), many=True
                ).data
                user_data["worker_profile"] = worker_profile
            elif hasattr(user, "client_profile"):
                client_profile = ClientProfileSerializer(user.client_profile).data
                user_data["client_profile"] = client_profile
        except Exception as e:
            return Response(
                f"Error enriching user data: {e}", status=status.HTTP_400_BAD_REQUEST
            )

        return user_data


class LoginView(BaseLoginView, generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Generate JWT token
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Enrich user data
        user_data = self.enrich_user_data(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": access_token,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )


class GoogleLoginView(BaseLoginView, generics.GenericAPIView):
    serializer_class = GoogleLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]

        # Exchange the authorization code for an access token
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_json = token_response.json()
        access_token = token_json.get("access_token")

        if not access_token:
            return Response(
                {"error": "Failed to obtain access token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use the access token to obtain user info
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            params={"access_token": access_token},
        )
        user_info = user_info_response.json()

        email = user_info.get("email")
        first_name = user_info.get("given_name")
        last_name = user_info.get("family_name")
        google_id = user_info.get("id")
        picture_url = user_info.get("picture")
        verified_email = user_info.get("verified_email", False)

        if not email:
            return Response(
                {"error": "Failed to obtain user email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "google_id": google_id,
                "picture_url": picture_url,
                "verified_email": verified_email,
                "is_active": True,
            },
        )

        if not created:
            user.first_name = first_name
            user.last_name = last_name
            user.google_id = google_id
            user.picture_url = picture_url
            user.verified_email = verified_email
            user.save()

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Enrich user data
        user_data = self.enrich_user_data(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": access_token,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )


class PINLoginView(BaseLoginView, generics.GenericAPIView):
    serializer_class = PINLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data.get("phone_number")
        code_pin = serializer.validated_data.get("code_pin")

        try:
            user = User.objects.get(phone_number=phone_number)

            if code_pin and user.code_pin != code_pin:
                return Response(
                    {"code_pin": "Invalid PIN"}, status=status.HTTP_400_BAD_REQUEST
                )

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # Enrich user data
            user_data = self.enrich_user_data(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": access_token,
                    "user": user_data,
                },
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED
            )


class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """

    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response(
                    {"old_password": ["Wrong password."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Set new password
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            return Response(
                {"detail": "Password updated successfully."}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SetPasswordView(generics.UpdateAPIView):
    """
    An endpoint for setting a new password without requiring the old password.
    """

    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Set new password
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            return Response(
                {"detail": "Password set successfully."}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(generics.GenericAPIView):
    """
    An endpoint for requesting a password reset via OTP.
    """

    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            email_or_phone = serializer.data.get("email_or_phone")
            user = None
            if "@" in email_or_phone:
                try:
                    user = User.objects.get(email=email_or_phone)
                except User.DoesNotExist:
                    return Response(
                        {"detail": "User with this email does not exist."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                try:
                    user = User.objects.get(phone_number=email_or_phone)
                except User.DoesNotExist:
                    return Response(
                        {"detail": "User with this phone number does not exist."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Generate OTP and send via email or SMS
            otp_code = get_random_string(length=5, allowed_chars="1234567890")
            user.otp_code = otp_code
            user.otp_generated_at = timezone.now()
            user.save()

            if "@" in email_or_phone:
                send_password_reset_email(user.email, otp_code)
            else:
                send_whatsapp_message(user.phone_number, otp_code)

            return Response(
                {"detail": "OTP sent successfully."}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    An endpoint for confirming a password reset via OTP.
    """

    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            otp_code = serializer.data.get("otp_code")
            new_password = serializer.data.get("new_password")
            try:
                user = User.objects.get(otp_code=otp_code, is_active=True)
            except User.DoesNotExist:
                return Response(
                    {"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST
                )

            # Set new password
            user.set_password(new_password)
            user.otp_code = None
            user.otp_generated_at = None
            user.save()
            return Response(
                {"detail": "Password reset successfully."}, status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(views.APIView):
    """
    An endpoint for logging out a user by blacklisting their refresh token.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logout successful."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    An endpoint for retrieving the authenticated user's profile information.
    """

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        data = {
            "user": UserProfileSerializer(user).data,  # Serialize user base information
        }

        # Add WorkerProfile if it exists
        try:
            worker_profile = WorkerProfile.objects.get(user=user)
            data["worker_profile"] = {
                "title": worker_profile.title,
                "skills": worker_profile.skills,
                "experience": worker_profile.experience,
                "price": worker_profile.price,
                "frequency": worker_profile.frequency,
                "certifications": worker_profile.certifications,
                "available_for_hire": worker_profile.available_for_hire,
                "total_jobs_completed": worker_profile.total_jobs_completed,
                "previous_work_photos": [
                    photo.photo.url
                    for photo in worker_profile.previous_work_photos.all()
                ],
            }
        except WorkerProfile.DoesNotExist:
            pass

        # Add ClientProfile if it exists
        try:
            client_profile = ClientProfile.objects.get(user=user)
            data["client_profile"] = {
                "preferred_payment_method": client_profile.preferred_payment_method,
                "average_spent": client_profile.average_spent,
                "loyalty_points": client_profile.loyalty_points,
                "service_name": client_profile.service_name,
                "service_type": client_profile.service_type,
                "service_description": client_profile.service_description,
                "location_description": client_profile.location_description,
                "location_latitude": client_profile.location_latitude,
                "location_longitude": client_profile.location_longitude,
            }
        except ClientProfile.DoesNotExist:
            pass

        return Response(data, status=status.HTTP_200_OK)


class CodePINCreateView(generics.CreateAPIView):
    serializer_class = CodePINSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        code_pin = request.data.get("code_pin")
        user.code_pin = code_pin
        user.save()
        return Response(
            {"detail": "Code PIN created successfully."}, status=status.HTTP_201_CREATED
        )


class CodePINUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CodePINSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class CheckPhoneNumberView(APIView):
    permission_classes = [permissions.AllowAny]

    # check if phone number exist send true or false
    # c'est methode post
    def post(self, request, *args, **kwargs):
        phone_number = request.data.get("phone_number")
        user = User.objects.filter(phone_number=phone_number).exists()
        return Response({"exists": user}, status=status.HTTP_200_OK)
