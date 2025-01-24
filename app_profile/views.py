from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.serializers import UserSerializer

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
        print("Création d'un nouveau profil worker")
        serializer.save(user=self.request.user)

    def get_queryset(self):
        print("Récupération du queryset")
        queryset = super().get_queryset()
        
        is_favorite = self.request.query_params.get('is_favorite', None)
        if is_favorite and is_favorite.lower() == 'true':
            # Filtrer pour n'obtenir que les profils favoris
            favorite_worker_ids = FavoriteWorker.objects.filter(
                user=self.request.user
            ).values_list('worker_profile_id', flat=True)
            queryset = queryset.filter(id__in=favorite_worker_ids)
            
        print(f"Nombre de profils trouvés: {queryset.count()}")
        return self.add_favorite_field(queryset)

    def add_favorite_field(self, queryset):
        print("Ajout du champ is_favorite")
        for worker_profile in queryset:
            print(f"Vérification des favoris pour le profil {worker_profile.id}")
            is_favorite = FavoriteWorker.objects.filter(
                user=self.request.user, worker_profile=worker_profile
            ).exists()
            print(f"Is favorite: {is_favorite}")
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

        user_data = UserSerializer(user).data

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


# Suggestion de profile travailleur
class WorkerProfileSuggestionListView(generics.ListAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ProfilePagination

    def get_queryset(self):
        user = self.request.user
        if ClientProfile.objects.filter(user=user).exists():
            client_profile = ClientProfile.objects.get(user=user)
            queryset = WorkerProfile.objects.filter(category=client_profile.category)
        else:
            queryset = WorkerProfile.objects.all()
        queryset = self.add_favorite_field(queryset)
        print("###############")
        print(queryset)
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

    # Champs pour la recherche :
    # - title
    # - category
    # - user.first_name, user.last_name (ou leur concaténation)

    # Champs pour le filtrage :
    # - title
    # - category
    # - hourly_rate
    # - user.city

    def get_queryset(self):
        # Récupérer la requête de base
        queryset = super().get_queryset()

        # Appliquer la logique de recherche
        queryset = self.apply_search(queryset)

        # Appliquer la logique de filtrage
        queryset = self.apply_filters(queryset)

        # Ajouter le champ "is_favorite" aux résultats
        return self.add_favorite_field(queryset)

    def apply_search(self, queryset):
        """
        Applique la logique de recherche en fonction des champs définis.
        """
        search_query = self.request.query_params.get("search", "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(category__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                & Q(user__last_name__icontains=search_query)
            )
        return queryset

    def apply_filters(self, queryset):
        """
        Applique la logique de filtrage en fonction des champs définis.
        """
        # Filtrer par titre
        title = self.request.query_params.get("title", None)
        if title:
            queryset = queryset.filter(title__icontains=title)

        # Filtrer par catégorie
        category = self.request.query_params.get("category", None)
        if category:
            queryset = queryset.filter(category__icontains=category)

        # Filtrer par tarif horaire
        hourly_rate_min = self.request.query_params.get("hourly_rate_min", None)
        hourly_rate_max = self.request.query_params.get("hourly_rate_max", None)
        if hourly_rate_min:
            queryset = queryset.filter(hourly_rate__gte=hourly_rate_min)
        if hourly_rate_max:
            queryset = queryset.filter(hourly_rate__lte=hourly_rate_max)

        # Filtrer par ville de l'utilisateur
        city = self.request.query_params.get("city", None)
        if city:
            queryset = queryset.filter(user__city__icontains=city)

        return queryset

    def add_favorite_field(self, queryset):
        """
        Ajoute un champ "is_favorite" indiquant si un profil est marqué comme favori par l'utilisateur actuel.
        """
        user = self.request.user
        for worker_profile in queryset:
            worker_profile.is_favorite = FavoriteWorker.objects.filter(
                user=user, worker_profile=worker_profile
            ).exists()
        return queryset
