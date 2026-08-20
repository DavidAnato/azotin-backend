from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app_job.models import JobOffer
from authentication.models import UserSettings
from authentication.serializers import UserSerializer, UserSettingsSerializer

from .models import ClientProfile, FavoriteWorker, WorkerProfile
from .serializers import (
    ClientProfileSerializer,
    PreviousWorkPhotoSerializer,
    WorkerProfileSerializer,
    WorkerProfileSerializerForUpdate,
)

User = get_user_model()


class ProfilePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# Worker Profile Views
class WorkerProfileListCreateView(generics.ListCreateAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProfilePagination

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()

        is_favorite = self.request.query_params.get("is_favorite", None)
        if is_favorite and is_favorite.lower() == "true":
            # Filtrer pour n'obtenir que les profils favoris
            favorite_worker_ids = FavoriteWorker.objects.filter(
                user=self.request.user
            ).values_list("worker_profile_id", flat=True)
            queryset = queryset.filter(id__in=favorite_worker_ids)

        return self.add_favorite_field(queryset)

    def add_favorite_field(self, queryset):
        for worker_profile in queryset:
            is_favorite = FavoriteWorker.objects.filter(
                user=self.request.user, worker_profile=worker_profile
            ).exists()
            setattr(worker_profile, "is_favorite", is_favorite)
        return queryset


class WorkerProfileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )

        user_data = UserSerializer(user, context={"request": request}).data

        if hasattr(user, "worker_profile"):
            worker_profile = WorkerProfileSerializer(user.worker_profile).data
            worker_profile["previous_work_photos"] = PreviousWorkPhotoSerializer(
                user.worker_profile.previous_work_photos.all(), many=True
            ).data
            user_data["worker_profile"] = worker_profile
        elif hasattr(user, "client_profile"):
            client_profile = ClientProfileSerializer(user.client_profile).data
            user_data["client_profile"] = client_profile

        return Response(user_data, status=status.HTTP_200_OK)


# Client Profile Views
class ClientProfileListCreateView(generics.ListCreateAPIView):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProfilePagination

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


class UpdateWorkerProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, *args, **kwargs):
        user = request.user
        # Mise à jour partielle des données du modèle User
        user_serializer = UserSerializer(user, data=request.data, partial=True, context={"request": request})
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

        user_data = self.enrich_user_data(user, request)
        return Response(
            {"message": "Profile updated successfully.", "user": user_data},
            status=status.HTTP_200_OK,
        )

    def enrich_user_data(self, user, request=None):
        context = {"request": request} if request is not None else {}
        user_data = UserSerializer(user, context=context).data
        try:
            settings = UserSettings.objects.get(user=user)
            user_data["settings"] = UserSettingsSerializer(settings).data
        except UserSettings.DoesNotExist:
            user_data["settings"] = None
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
                f"Une erreur est survenue lors de la mise à jour du profil : {e}",
                status=status.HTTP_400_BAD_REQUEST,
            )

        return user_data


# Mise à jour du profil client
class UpdateClientProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, *args, **kwargs):
        user = request.user
        # Mise à jour partielle des données du modèle User
        user_serializer = UserSerializer(
            user, data=request.data, partial=True, context={"request": request}
        )
        if user_serializer.is_valid():
            user_serializer.save()
        else:
            return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Mise à jour ou création du ClientProfile
        client_profile, created = ClientProfile.objects.get_or_create(user=user)
        client_profile_serializer = ClientProfileSerializer(
            client_profile, data=request.data, partial=True
        )
        if client_profile_serializer.is_valid():
            client_profile_serializer.save()
        else:
            return Response(
                client_profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        user_data = self.enrich_user_data(user, request)
        return Response(
            {"message": "Profile updated successfully.", "user": user_data},
            status=status.HTTP_200_OK,
        )

    def enrich_user_data(self, user, request=None):
        context = {"request": request} if request is not None else {}
        user_data = UserSerializer(user, context=context).data
        try:
            settings = UserSettings.objects.get(user=user)
            user_data["settings"] = UserSettingsSerializer(settings).data
        except UserSettings.DoesNotExist:
            user_data["settings"] = None
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
                f"Une erreur est survenue lors de la mise à jour du profil : {e}",
                status=status.HTTP_400_BAD_REQUEST,
            )

        return user_data


# Suggestion de profile travailleur
class WorkerProfileSuggestionListView(generics.ListAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProfilePagination

    def get_queryset(self):
        user = self.request.user
        if ClientProfile.objects.filter(user=user).exists():
            # Récupérer les catégories des offres d'emploi du client
            job_categories = (
                JobOffer.objects.filter(client__user=user)
                .values_list("category", flat=True)
                .distinct()
            )
            # Filtrer les profils de travailleurs qui correspondent à ces catégories
            queryset = WorkerProfile.objects.filter(category__in=job_categories)
        else:
            queryset = WorkerProfile.objects.all()
        queryset = self.add_favorite_field(queryset)
        return queryset

    def add_favorite_field(self, queryset):
        for worker_profile in queryset:
            worker_profile.is_favorite = FavoriteWorker.objects.filter(
                user=self.request.user, worker_profile=worker_profile
            ).exists()
        return queryset


# Suggestion de profile travailleur par job
class WorkerProfileSuggestionByJobListView(generics.ListAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProfilePagination

    def get_queryset(self):
        job_id = self.kwargs.get("job_id")
        try:
            job_offer = JobOffer.objects.get(id=job_id)
            # Filtrer les profils de travailleurs qui correspondent au titre du job
            queryset = WorkerProfile.objects.filter(
                Q(title=job_offer.sub_category) | Q(job_types=job_offer.sub_category)
            ).distinct()
        except JobOffer.DoesNotExist:
            queryset = WorkerProfile.objects.none()

        queryset = self.add_favorite_field(queryset)
        return queryset

    def add_favorite_field(self, queryset):
        for worker_profile in queryset:
            worker_profile.is_favorite = FavoriteWorker.objects.filter(
                user=self.request.user, worker_profile=worker_profile
            ).exists()
        return queryset


# Favoris travailleur
class FavoriteWorkerToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        worker_profile_id = kwargs.get("worker_profile_id")
        try:
            worker_profile = WorkerProfile.objects.get(id=worker_profile_id)
        except WorkerProfile.DoesNotExist:
            return Response(
                {"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND
            )
        favorite, created = FavoriteWorker.objects.get_or_create(
            user=request.user, worker_profile=worker_profile
        )

        if not created:
            favorite.delete()
            return Response(
                {"message": "Worker profile removed from favorites."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Worker profile added to favorites successfully."},
            status=status.HTTP_201_CREATED,
        )


# Recherche de travailleur
class WorkerProfileSearchView(generics.ListAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProfilePagination

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_search(queryset)
        queryset = self.apply_filters(queryset)
        return self.add_favorite_field(queryset)

    def apply_search(self, queryset):
        search_query = self.request.query_params.get("query", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__name__icontains=search_query)
                | Q(job_types__name__icontains=search_query)
                | Q(category__name__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
            ).distinct()
        return queryset

    def apply_filters(self, queryset):
        title = self.request.query_params.get("title", None)
        if title:
            queryset = queryset.filter(
                Q(title__name__icontains=title) | Q(job_types__name__icontains=title)
            ).distinct()

        category = self.request.query_params.get("category", None)
        if category:
            queryset = queryset.filter(category__name__icontains=category)

        price_frequency = self.request.query_params.get("price_frequency", "hour")

        price_min = self.request.query_params.get("min_price", None)
        if price_min:
            price_min_converted = self.convert_price(
                float(price_min), price_frequency, "hour"
            )
            queryset = queryset.filter(price__gte=price_min_converted)

        price_max = self.request.query_params.get("max_price", None)
        if price_max:
            price_max_converted = self.convert_price(
                float(price_max), price_frequency, "hour"
            )
            queryset = queryset.filter(price__lte=price_max_converted)

        city = self.request.query_params.get("location", None)
        if city:
            queryset = queryset.filter(user__city__icontains=city)

        return queryset

    def add_favorite_field(self, queryset):
        user = self.request.user
        for worker_profile in queryset:
            worker_profile.is_favorite = FavoriteWorker.objects.filter(
                user=user, worker_profile=worker_profile
            ).exists()
        return queryset

    @staticmethod
    def convert_price(price, from_frequency, to_frequency):
        conversion_rates = {
            "hour": {"hour": 1, "day": 8, "week": 40, "month": 160},
            "day": {"hour": 1 / 8, "day": 1, "week": 5, "month": 20},
            "week": {"hour": 1 / 40, "day": 1 / 5, "week": 1, "month": 4},
            "month": {"hour": 1 / 160, "day": 1 / 20, "week": 1 / 4, "month": 1},
        }
        return price * conversion_rates[from_frequency][to_frequency]
