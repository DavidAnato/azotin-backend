# Third-party imports
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import generics, permissions, status, views
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from app_profile.models import ClientProfile, WorkerProfile
from app_profile.serializers import (
    ClientProfileSerializer,
    PreviousWorkPhotoSerializer,
    WorkerProfileSerializer,
)
from authentication.models import KycSubmission, UserSettings
from authentication.kyc import effective_kyc_status, get_kyc_submission

from .otp_service import otp_service_ready, send_otp, verify_otp
from .serializers import (
    ChangePasswordSerializer,
    CodePINSerializer,
    DeleteAccountSerializer,
    EmailValidateRequestSerializer,
    GoogleLoginSerializer,
    KYCSerializer,
    LoginSerializer,
    OTPVerificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PhoneNumberValidateConfirmSerializer,
    PhoneNumberValidateRequestSerializer,
    PINLoginSerializer,
    RegisterSerializer,
    UserSerializer,
    UserSettingsSerializer,
)

# Local imports
from .utils import (
    build_activation_link,
    frontend_activation_success_url,
    send_activation_email,
    send_password_reset_email,
    send_whatsapp_message,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _otp_unavailable_response():
    return Response(
        {
            "error": "Le service OTP GetOurVoice n'est pas configuré "
            "(GETOURVOICE_API_KEY).",
            "code": "otp_service_unavailable",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _otp_failure_response(payload):
    if (payload or {}).get("code") == "otp_service_unavailable":
        return Response(
            {
                "error": payload.get(
                    "error",
                    "Le service OTP GetOurVoice n'est pas configuré.",
                ),
                "code": "otp_service_unavailable",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    body = {
        "error": (payload or {}).get("error", "Échec de l'envoi du code OTP."),
    }
    if (payload or {}).get("details"):
        body["details"] = payload["details"]
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def create_user_profile(user, profile_type: str) -> None:
    """Crée le profil client ou travailleur + paramètres utilisateur."""
    UserSettings.objects.get_or_create(user=user)
    if profile_type == "worker":
        WorkerProfile.objects.get_or_create(user=user)
    elif profile_type == "employer":
        ClientProfile.objects.get_or_create(user=user)
    else:
        raise ValueError(f"Type de profil invalide : {profile_type}")
    if getattr(user, "profile_type", "") != profile_type:
        user.profile_type = profile_type
        user.save(update_fields=["profile_type"])


class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        raw = request.data
        try:
            raw_dict = raw.dict() if hasattr(raw, "dict") else dict(raw)
        except Exception:
            raw_dict = {"_unreadable": repr(raw)[:500]}

        phone_raw = raw_dict.get("phone_number")
        logger.warning(
            "[register] reçu content_type=%s method=%s keys=%s "
            "phone_number=%r phone_type=%s phone_len=%s "
            "first_name=%r last_name=%r profile_type=%r channel=%r body=%s",
            getattr(request, "content_type", None),
            request.method,
            list(raw_dict.keys()),
            phone_raw,
            type(phone_raw).__name__,
            len(str(phone_raw)) if phone_raw is not None else None,
            raw_dict.get("first_name"),
            raw_dict.get("last_name"),
            raw_dict.get("profile_type"),
            raw_dict.get("channel"),
            {k: raw_dict.get(k) for k in raw_dict if k != "password"},
        )

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "[register] validation échouée errors=%s phone=%r body=%s",
                serializer.errors,
                phone_raw,
                raw_dict,
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            phone_number = serializer.validated_data.get("phone_number")
            channel = serializer.validated_data.get("channel") or "sms"
            logger.warning(
                "[register] validé phone=%r channel=%s profile_type=%s",
                phone_number,
                channel,
                serializer.validated_data.get("profile_type"),
            )
            if phone_number:
                if not otp_service_ready():
                    logger.error("[register] OTP service non configuré (GETOURVOICE_API_KEY)")
                    return _otp_unavailable_response()

                success, response = send_otp(
                    phone_number=phone_number,
                    api_key=settings.GETOURVOICE_API_KEY,
                    channel=channel,
                )

                if not success:
                    logger.error(
                        "[register] échec envoi OTP phone=%r otp_response=%s",
                        phone_number,
                        response,
                    )
                    return _otp_failure_response(response)

                # Si l'envoi OTP a réussi, créer l'utilisateur
                user = serializer.save()
                user.is_active = False
                user.save()

                create_user_profile(
                    user, serializer.validated_data["profile_type"]
                )

                logger.warning(
                    "[register] OK user_id=%s phone=%r channel=%s",
                    user.id,
                    phone_number,
                    channel,
                )
                payload = {
                    "message": "Code OTP envoyé avec succès.",
                    "channel": channel,
                }
                if getattr(settings, "OTP_SKIP_SMS", False):
                    payload["dev_otp"] = getattr(settings, "DEV_OTP_CODE", "00000")
                return Response(payload, status=status.HTTP_201_CREATED)
            else:
                # Si pas de numéro de téléphone, créer l'utilisateur directement
                user = serializer.save()
                logger.warning("[register] OK sans téléphone user_id=%s", user.id)
                return Response(
                    {"message": "Compte créé avec succès."},
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            logger.exception(
                "[register] exception phone=%r err=%s",
                serializer.validated_data.get("phone_number")
                if serializer.validated_data
                else phone_raw,
                e,
            )
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
        channel = serializer.validated_data.get("channel") or "sms"

        try:
            # Vérifier si l'utilisateur existe
            User.objects.get(phone_number=phone_number)

            if not otp_service_ready():
                return _otp_unavailable_response()

            # Envoyer l'OTP via GetOurVoice (SMS)
            success, response = send_otp(
                phone_number=phone_number,
                api_key=settings.GETOURVOICE_API_KEY,
                channel=channel,
            )

            # Vérifier si l'envoi a réussi
            if not success:
                logger.error(
                    "Demande OTP: échec envoi (%s)",
                    (response or {}).get("error"),
                )
                return _otp_failure_response(response)

            payload = {
                "message": "Code OTP envoyé avec succès.",
                "channel": channel,
            }
            if getattr(settings, "OTP_SKIP_SMS", False):
                payload["dev_otp"] = getattr(settings, "DEV_OTP_CODE", "00000")
            return Response(payload, status=status.HTTP_200_OK)
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

            if not otp_service_ready():
                return _otp_unavailable_response()

            # Vérifier l'OTP via GetOurVoice
            success, response = verify_otp(
                phone_number=phone_number,
                code=otp_code,
                api_key=settings.GETOURVOICE_API_KEY,
            )

            if not success:
                if (response or {}).get("code") == "otp_service_unavailable":
                    return _otp_failure_response(response)
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
        serializer = self.get_serializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        email = (serializer.validated_data.get("email") or "").strip()
        if not email and request.user.is_authenticated:
            email = request.user.email or ""
        if not email:
            return Response(
                {"error": "Adresse email requise."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Aucun compte trouvé avec cette adresse email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.verified_email:
            return Response(
                {"error": "Cette adresse email est déjà vérifiée."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_code = get_random_string(length=5, allowed_chars="1234567890")
        user.otp_code = otp_code
        user.otp_generated_at = timezone.now()
        user.save(update_fields=["otp_code", "otp_generated_at"])

        activation_link = build_activation_link(request, user.email, otp_code)
        sent = send_activation_email(user.email, otp_code, activation_link)
        if not sent:
            return Response(
                {
                    "error": "Impossible d'envoyer l'email de vérification. Réessayez plus tard.",
                    "code": "email_send_failed",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"message": "Un email de vérification a été envoyé."},
            status=status.HTTP_201_CREATED,
        )


class EmailActivateView(generics.GenericAPIView):
    serializer_class = OTPVerificationSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        otp_code = request.query_params.get("otp_code")
        email = request.query_params.get("email")

        if not otp_code or not email:
            return Response(
                {"error": "Le code OTP et l'email sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activation_response = self.activate_account(email, otp_code)
        if activation_response.status_code == status.HTTP_200_OK:
            return redirect(frontend_activation_success_url())
        return activation_response

    def post(self, request, *args, **kwargs):
        return self.activate_account(
            request.data.get("email"), request.data.get("otp_code")
        )

    def activate_account(self, email, otp_code):
        if not email or not otp_code:
            return Response(
                {"error": "Le code OTP et l'email sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Utilisateur introuvable."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.verified_email:
            return Response(
                {"message": "Cette adresse email est déjà vérifiée."},
                status=status.HTTP_200_OK,
            )
        if user.otp_code != otp_code:
            return Response(
                {"error": "Code OTP invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            user.otp_generated_at
            and user.otp_generated_at + timedelta(hours=3) < timezone.now()
        ):
            return Response(
                {"error": "Le code OTP a expiré. Demandez-en un nouveau."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.verified_email = True
        user.otp_code = None
        user.otp_generated_at = None
        user.save(
            update_fields=[
                "is_active",
                "verified_email",
                "otp_code",
                "otp_generated_at",
            ]
        )

        return Response(
            {"message": "Votre compte a été activé avec succès."},
            status=status.HTTP_200_OK,
        )


class BaseLoginView(APIView):
    """
    Base class for login views to enrich user data with profile-specific information.
    """

    def enrich_user_data(self, user, request=None):
        context = {"request": request} if request is not None else {}
        user_data = UserSerializer(user, context=context).data
        user_data["kyc_status"] = effective_kyc_status(user)
        user_data["is_certified"] = bool(user.is_certified) or effective_kyc_status(
            user
        ) == "approved"
        try:
            settings = UserSettings.objects.get(user=user)
            user_data["settings"] = UserSettingsSerializer(settings).data
        except UserSettings.DoesNotExist:
            user_data["settings"] = None

        try:
            worker = WorkerProfile.objects.filter(user=user).first()
            client = ClientProfile.objects.filter(user=user).first()
            if worker is not None:
                worker_profile = WorkerProfileSerializer(worker).data
                worker_profile["previous_work_photos"] = PreviousWorkPhotoSerializer(
                    worker.previous_work_photos.all(), many=True
                ).data
                user_data["worker_profile"] = worker_profile
            elif client is not None:
                user_data["client_profile"] = ClientProfileSerializer(client).data
        except Exception as e:
            # Ne jamais renvoyer un Response ici : le caller l’embarque dans le JSON user
            # et provoquait un 500 côté pin-login / login.
            logger.exception("Error enriching user data for user_id=%s: %s", user.pk, e)
            user_data.setdefault("worker_profile", None)
            user_data.setdefault("client_profile", None)

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
        user_data = self.enrich_user_data(user, request)

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
        user_data = self.enrich_user_data(user, request)

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
            user_data = self.enrich_user_data(user, request)

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
                if not send_password_reset_email(user.email, otp_code):
                    return Response(
                        {
                            "detail": "Impossible d'envoyer l'email. Réessayez plus tard.",
                            "code": "email_send_failed",
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
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


class EnsureProfileView(BaseLoginView, APIView):
    """
    Crée le profil client/travailleur si absent (comptes inscrits avant correctif).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        profile_type = request.data.get("profile_type")
        if profile_type not in ("worker", "employer"):
            return Response(
                {"error": "profile_type requis : worker ou employer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        has_profile = WorkerProfile.objects.filter(user=user).exists() or (
            ClientProfile.objects.filter(user=user).exists()
        )
        if not has_profile:
            try:
                create_user_profile(user, profile_type)
            except ValueError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"user": self.enrich_user_data(user, request)},
            status=status.HTTP_200_OK,
        )


class UserProfileView(BaseLoginView):
    """
    Profil de l'utilisateur authentifié — même forme enrichie que le login.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user_data = self.enrich_user_data(request.user, request)
        return Response({"user": user_data}, status=status.HTTP_200_OK)


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


class UserSettingsView(APIView):
    """
    Vue pour récupérer et mettre à jour les paramètres utilisateur
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, user):
        settings, created = UserSettings.objects.get_or_create(user=user)
        return settings

    def get(self, request, *args, **kwargs):
        settings = self.get_object(request.user)
        serializer = UserSettingsSerializer(settings)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        settings = self.get_object(request.user)
        serializer = UserSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteAccountView(APIView):
    """Désactive le compte courant (soft-delete). Ne bascule jamais vers un autre utilisateur."""

    permission_classes = [IsAuthenticated]
    serializer_class = DeleteAccountSerializer

    def post(self, request, *args, **kwargs):
        return self._deactivate(request)

    def delete(self, request, *args, **kwargs):
        return self._deactivate(request)

    def _deactivate(self, request):
        user = request.user
        serializer = DeleteAccountSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=False)
        refresh_token = ""
        if serializer.is_valid():
            refresh_token = (
                serializer.validated_data.get("refresh_token")
                or serializer.validated_data.get("refresh")
                or ""
            )
        if not refresh_token:
            refresh_token = (
                request.data.get("refresh_token")
                or request.data.get("refresh")
                or ""
            )

        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except Exception:
                logger.info(
                    "Impossible de blacklister le refresh token à la suppression."
                )

        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )

            for outstanding in OutstandingToken.objects.filter(user_id=user.pk):
                BlacklistedToken.objects.get_or_create(token=outstanding)
        except Exception:
            logger.info("Impossible de blacklister les sessions à la suppression.")

        stamp = timezone.now().strftime("%Y%m%d%H%M%S")
        user.is_active = False
        user.email = f"deleted+{user.id}+{stamp}@deleted.azotin.local"
        user.phone_number = f"d{user.id}{stamp}"[:20]
        user.username = f"deleted_{user.id}_{stamp}"[:100]
        user.first_name = "Utilisateur"
        user.last_name = "Supprimé"
        user.google_id = None
        user.code_pin = None
        user.otp_code = None
        user.save()

        # Pas de tokens, pas d'autre user : le client doit uniquement se déconnecter.
        return Response(
            {"detail": "Compte désactivé."},
            status=status.HTTP_200_OK,
        )


class KYCView(APIView):
    """Consultation et dépôt KYC (pièce d'identité, selfie, nom)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _payload(self, user, submission=None):
        submission = submission if submission is not None else get_kyc_submission(user)
        status_value = effective_kyc_status(user)
        return {
            "kyc_status": status_value,
            "kyc_submitted_at": submission.submitted_at if submission else None,
            "is_certified": bool(user.is_certified) or status_value == "approved",
            "id_type": (submission.id_type if submission else "") or "",
            "id_number": (submission.id_number if submission else "") or "",
            "has_id_document": bool(submission and submission.id_document),
            "has_selfie": bool(submission and submission.selfie),
        }

    def get(self, request, *args, **kwargs):
        return Response(self._payload(request.user))

    def post(self, request, *args, **kwargs):
        serializer = KYCSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        data = serializer.validated_data

        submission, _ = KycSubmission.objects.get_or_create(user=user)
        submission.id_type = data.get("id_type") or submission.id_type
        submission.id_number = data.get("id_number") or submission.id_number

        full_name = (data.get("full_name") or "").strip()
        name_fields = []
        if full_name:
            submission.full_name = full_name
            parts = full_name.split(None, 1)
            user.first_name = parts[0]
            name_fields.append("first_name")
            if len(parts) > 1:
                user.last_name = parts[1]
                name_fields.append("last_name")
            if name_fields:
                user.save(update_fields=name_fields)

        doc = data.get("id_document") or data.get("piece")
        selfie = data.get("selfie")
        if doc:
            submission.id_document = doc
        if selfie:
            submission.selfie = selfie

        submission.submitted_at = timezone.now()
        if user.is_certified or submission.status == "approved":
            submission.status = "approved"
            submission.reviewed_at = submission.reviewed_at or timezone.now()
        else:
            submission.status = "pending"
            submission.reviewed_at = None
        submission.save()

        body = self._payload(user, submission)
        body["detail"] = "Dossier KYC enregistré."
        return Response(body, status=status.HTTP_200_OK)
