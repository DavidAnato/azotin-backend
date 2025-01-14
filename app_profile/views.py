from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.serializers import UserSerializer

from .models import ClientProfile, WorkerProfile
from .serializers import (
    ClientProfileSerializer,
    PreviousWorkPhotoSerializer,
    WorkerProfileSerializer,
    WorkerProfileSerializerForUpdate,
)


# Worker Profile Views
class WorkerProfileListCreateView(generics.ListCreateAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WorkerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        worker_profile = super().get_object()
        if worker_profile.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this Worker Profile.")
        return worker_profile


# Client Profile Views
class ClientProfileListCreateView(generics.ListCreateAPIView):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ClientProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        client_profile = super().get_object()
        if client_profile.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this Client Profile.")
        return client_profile


# Update request user profile

# Model User
# email
# first_name
# last_name
# phone_number
# bio
# city
# profile_picture
# linkedin
# twitter
# facebook
# instagram
# website
# localisation_longitude
# localisation_latitude

# Model WorkerProfile
# title
# category
# skills
# hourly_rate

# PreviousWorkPhoto (many)
# worker_profile (FK)
# photo


class UpdateUserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, *args, **kwargs):
        user = request.user
        print(request.data)
        # Mise à jour partielle des données du modèle User
        user_serializer = UserSerializer(user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
        else:
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Mise à jour ou création du WorkerProfile
        worker_profile, created = WorkerProfile.objects.get_or_create(user=user)
        worker_profile_serializer = WorkerProfileSerializerForUpdate(
            worker_profile, data=request.data, partial=True
        )
        if worker_profile_serializer.is_valid():
            worker_profile_serializer.save()
        else:
            return Response(
                worker_profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        # Ajout des photos de PreviousWorkPhoto
        if "previous_work_photos" in request.FILES:
            photos = request.FILES.getlist("previous_work_photos")
            for photo in photos:
                photo_data = {"worker_profile": worker_profile.id, "photo": photo}
                photo_serializer = PreviousWorkPhotoSerializer(data=photo_data)
                if photo_serializer.is_valid():
                    photo_serializer.save()
                else:
                    return Response(
                        photo_serializer.errors, status=status.HTTP_400_BAD_REQUEST
                    )

        user_data = self.enrich_user_data(user)
        return Response(
            {"message": "Profile updated successfully.", "user": user_data},
            status=status.HTTP_200_OK,
        )

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
            print(f"Error enriching user data: {e}")

        return user_data
