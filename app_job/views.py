# from math import atan2, cos, radians, sin, sqrt

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import ValidationError
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app_profile.models import ClientProfile, WorkerProfile

from .models import Category, Job, JobApplication, JobFavorite, JobOffer, SubCategory
from .serializers import (
    CategorySerializer,
    JobApplicationSerializer,
    JobOfferSerializer,
    JobSerializer,
    SubCategorySerializer,
)

User = get_user_model()


# Pagination
class JobPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryAndSubCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = Category.objects.all()
        sub_categories = SubCategory.objects.all()

        # Serialize the data
        category_serializer = CategorySerializer(categories, many=True)
        sub_category_serializer = SubCategorySerializer(sub_categories, many=True)

        # Return the response with serialized data
        return Response(
            {
                "categories": category_serializer.data,
                "sub_categories": sub_category_serializer.data,
            }
        )


class JobOfferListCreateView(generics.ListCreateAPIView):
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        queryset = JobOffer.objects.filter(is_filled=False).order_by("-created_at")
        client_id = self.request.query_params.get("client_id", None)
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset

    def list(self, request, *args, **kwargs):
        # Filtrer les offres favorites si le paramètre is_favorite est passé
        is_favorite = request.query_params.get("is_favorite", None)

        queryset = self.filter_queryset(self.get_queryset())

        if is_favorite is not None:
            queryset = queryset.filter(job_favorites__user=request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            self.add_custom_fields(serializer.data, request.user)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        self.add_custom_fields(serializer.data, request.user)
        return Response(serializer.data)

    def add_custom_fields(self, data_list, user):
        """
        Ajoute les champs personnalisés `status`, `is_favorite`,
        `applicant_count` et `applicants` aux données de chaque offre.
        """
        # Précharger les relations nécessaires
        job_offer_ids = [data["id"] for data in data_list]
        job_offers = JobOffer.objects.filter(id__in=job_offer_ids).prefetch_related(
            "job_favorites",  # Pour les favoris
            "applications__worker__user",  # Pour les candidatures
            "job",  # Pour vérifier le statut de l'offre
        )

        # Créer un dictionnaire pour un accès rapide
        job_offer_dict = {job.id: job for job in job_offers}

        for data in data_list:
            job_offer = job_offer_dict.get(data["id"])
            if not job_offer:
                continue

            # Déterminer le statut de l'offre de la même manière que dans JobOfferDetailView
            if Job.objects.filter(
                job_offer=job_offer, worker__user=user, completed=False
            ).exists():
                data["status"] = "in_progress"
            elif JobApplication.objects.filter(
                job_offer=job_offer, worker__user=user
            ).exists():
                data["status"] = "applied"
            elif Job.objects.filter(job_offer=job_offer, completed=True).exists():
                data["status"] = "completed"
            elif Job.objects.filter(job_offer=job_offer, client__user=user).exists():
                data["status"] = "in_progress"
            else:
                data["status"] = False

            # Ajouter les informations supplémentaires
            data["is_favorite"] = job_offer.job_favorites.filter(user=user).exists()
            data["applicant_count"] = job_offer.applications.count()
            # Je veux un try catch pour éviter les erreurs si le worker n'a pas de profile_picture
            data["applicants"] = []
            for app in job_offer.applications.all():
                try:
                    profile_picture = (
                        str(app.worker.user.profile_picture)
                        if app.worker.user.profile_picture
                        else None
                    )
                    picture_url = (
                        str(app.worker.user.picture_url)
                        if hasattr(app.worker.user, "picture_url")
                        else None
                    )
                except (UnicodeDecodeError, AttributeError):
                    profile_picture = None
                    picture_url = None

                data["applicants"].append(
                    {
                        "id": app.worker.user.id,
                        "first_name": app.worker.user.first_name,
                        "last_name": app.worker.user.last_name,
                        "email": app.worker.user.email,
                        "phone_number": app.worker.user.phone_number,
                        "profile_picture": profile_picture,
                        "picture_url": picture_url,
                    }
                )

    def perform_create(self, serializer):
        client_profile = ClientProfile.objects.get(user=self.request.user)

        # Récupérer la sous-catégorie directement des données validées
        sub_category_id = self.request.data.get("sub_category")
        try:
            sub_category = SubCategory.objects.get(id=sub_category_id)
            serializer.save(
                client=client_profile,
                sub_category=sub_category,
                category=sub_category.category,  # Ajout de la catégorie parent
            )
        except SubCategory.DoesNotExist:
            raise ValidationError({"sub_category": ["Sous-catégorie invalide."]})


class JobOfferDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        job_offer = self.get_object()
        serializer = self.get_serializer(job_offer)

        # Convertir les données sérialisées en un dictionnaire pour ajouter des champs supplémentaires
        data = serializer.data
        self.add_custom_fields([job_offer], request.user)

        # Ajouter les champs supplémentaires à la réponse
        data["status"] = job_offer.status
        data["is_favorite"] = job_offer.is_favorite
        data["applicant_count"] = job_offer.applicant_count
        data["applicants"] = job_offer.applicants

        return Response(data)

    def add_custom_fields(self, data_list, user):
        for data in data_list:
            job_offer = data
            if Job.objects.filter(
                job_offer=job_offer, worker__user=user, completed=False
            ).exists():
                job_offer.status = "in_progress"
            elif JobApplication.objects.filter(
                job_offer=job_offer, worker__user=user
            ).exists():
                job_offer.status = "applied"
            elif Job.objects.filter(job_offer=job_offer, completed=True).exists():
                job_offer.status = "completed"
            elif Job.objects.filter(job_offer=job_offer, client__user=user).exists():
                job_offer.status = "in_progress"
            else:
                job_offer.status = False

            job_offer.is_favorite = JobFavorite.objects.filter(
                user=user, job_offer=job_offer
            ).exists()

            job_offer.applicant_count = JobApplication.objects.filter(
                job_offer=job_offer
            ).count()

            # Sécuriser l'accès aux champs potentiellement problématiques
            job_offer.applicants = []
            for app in JobApplication.objects.filter(job_offer=job_offer):
                try:
                    profile_picture = (
                        str(app.worker.user.profile_picture)
                        if app.worker.user.profile_picture
                        else None
                    )
                except (UnicodeDecodeError, AttributeError):
                    profile_picture = None

                try:
                    picture_url = (
                        str(app.worker.user.picture_url)
                        if hasattr(app.worker.user, "picture_url")
                        else None
                    )
                except (UnicodeDecodeError, AttributeError):
                    picture_url = None

                job_offer.applicants.append(
                    {
                        "id": app.worker.user.id,
                        "first_name": app.worker.user.first_name,
                        "last_name": app.worker.user.last_name,
                        "email": app.worker.user.email,
                        "phone_number": app.worker.user.phone_number,
                        "profile_picture": profile_picture,
                        "picture_url": picture_url,
                    }
                )


# Job Application Views
class JobApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        return JobApplication.objects.filter(job_offer__id=self.kwargs["job_offer_id"])

    def perform_create(self, serializer):
        worker_profile = WorkerProfile.objects.get(user=self.request.user)
        job_offer = JobOffer.objects.get(id=self.kwargs["job_offer_id"])
        if job_offer.is_filled:
            raise PermissionDenied("This job offer is already filled.")
        if not WorkerProfile.objects.filter(user=self.request.user).exists():
            raise PermissionDenied("You are not allowed to apply to this job.")
        if JobApplication.objects.filter(
            worker=worker_profile, job_offer=job_offer
        ).exists():
            raise PermissionDenied("You have already applied to this job.")
        serializer.save(worker=worker_profile, job_offer=job_offer)


class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        job_application = super().get_object()
        if job_application.worker.user != self.request.user:
            raise PermissionDenied(
                "You are not allowed to access this Job Application."
            )
        return job_application


# Job Creation and Detail Views
class JobCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_application_id):
        job_application = JobApplication.objects.get(id=job_application_id)
        if job_application.job_offer.client.user != request.user:
            raise PermissionDenied(
                "You are not allowed to create a job from this application."
            )
        if job_application.status != "pending":
            return Response(
                {"detail": "This application has already been processed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_application.status = "accepted"
        job_application.save()

        # Mark the job offer as filled
        job_application.job_offer.is_filled = True
        job_application.job_offer.save()

        # Create the Job instance
        job = Job.objects.create(
            job_offer=job_application.job_offer,
            client=job_application.job_offer.client,
            worker=job_application.worker,
            description=job_application.job_offer.description,
            location=job_application.job_offer.location,
            price=job_application.proposed_price,
        )

        serializer = JobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        job = super().get_object()
        if (
            job.client.user != self.request.user
            and job.worker.user != self.request.user
        ):
            raise PermissionDenied("You are not allowed to access this job.")
        return job


# l'historique des emplois
class JobHistoryListView(generics.ListAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        user = self.request.user
        is_completed = self.request.query_params.get("is_completed", None)

        # Vérifier si l'utilisateur a un profil client
        if hasattr(user, "client_profile"):
            queryset = Job.objects.filter(client=user.client_profile)

        # Vérifier si l'utilisateur a un profil travailleur
        elif hasattr(user, "worker_profile"):
            queryset = Job.objects.filter(worker=user.worker_profile)

        else:
            return Job.objects.none()

        if is_completed == "true":
            queryset = queryset.filter(completed=True)

        return queryset


class JobOfferSuggestionListView(generics.ListAPIView):
    queryset = JobOffer.objects.filter(is_filled=False)
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        user = self.request.user

        if WorkerProfile.objects.filter(user=user).exists():
            worker_profile = WorkerProfile.objects.get(user=user)

            # Filtrage initial
            jobs_offers = JobOffer.objects.filter(is_filled=False)

            # Filtrer par catégorie
            if worker_profile.category:
                jobs_offers = jobs_offers.filter(category=worker_profile.category)

            # Filtrer par sous-catégorie
            if worker_profile.title:
                sub_category_offers = JobOffer.objects.filter(
                    sub_category=worker_profile.title
                )
                # Union des résultats
                jobs_offers = jobs_offers | sub_category_offers

            # Vérifier les résultats finaux
            if not jobs_offers.exists():
                return JobOffer.objects.none()
            else:
                return jobs_offers
        else:
            return JobOffer.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            self.add_custom_fields(serializer.data, request.user)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        self.add_custom_fields(serializer.data, request.user)
        return Response(serializer.data)

    def add_custom_fields(self, data_list, user):
        """
        Ajoute les champs personnalisés `status`, `is_favorite`,
        `applicant_count` et `applicants` aux données de chaque offre.
        """
        # Précharger les relations nécessaires
        job_offer_ids = [data["id"] for data in data_list]
        job_offers = JobOffer.objects.filter(id__in=job_offer_ids).prefetch_related(
            "job_favorites",  # Pour les favoris
            "applications__worker__user",  # Pour les candidatures
            "job",  # Pour vérifier le statut de l'offre
        )

        # Créer un dictionnaire pour un accès rapide
        job_offer_dict = {job.id: job for job in job_offers}

        for data in data_list:
            job_offer = job_offer_dict.get(data["id"])
            if not job_offer:
                continue

            # Déterminer le statut de l'offre
            if Job.objects.filter(job_offer=job_offer, worker__user=user).exists():
                data["status"] = "in_progress"
            elif JobApplication.objects.filter(
                job_offer=job_offer, worker__user=user
            ).exists():
                data["status"] = "applied"
            elif Job.objects.filter(job_offer=job_offer, completed=True).exists():
                data["status"] = "completed"
            else:
                data["status"] = None

            # Ajouter les informations supplémentaires
            data["is_favorite"] = job_offer.job_favorites.filter(user=user).exists()
            data["applicant_count"] = job_offer.applications.count()
            # Je veux un try catch pour éviter les erreurs si le worker n'a pas de profile_picture
            data["applicants"] = []
            for app in job_offer.applications.all():
                try:
                    profile_picture = (
                        str(app.worker.user.profile_picture)
                        if app.worker.user.profile_picture
                        else None
                    )
                    picture_url = (
                        str(app.worker.user.picture_url)
                        if hasattr(app.worker.user, "picture_url")
                        else None
                    )
                except (UnicodeDecodeError, AttributeError):
                    profile_picture = None
                    picture_url = None

                data["applicants"].append(
                    {
                        "id": app.worker.user.id,
                        "first_name": app.worker.user.first_name,
                        "last_name": app.worker.user.last_name,
                        "email": app.worker.user.email,
                        "phone_number": app.worker.user.phone_number,
                        "profile_picture": profile_picture,
                        "picture_url": picture_url,
                    }
                )


# Recherche de jobs par les champs suivants :
# title
# description
# catégorie
# sous-catégorie
# Filtres par les champs suivants :
# - catégorie
# - sous-catégorie
# - localisation
# - prix minimum
# - prix maximum
# - date de service
# - type de contrat

# Recherche de jobs par les champs suivants :
# - query (prend en compte title, description, category, sub_category)
# Filtres par les champs suivants :
# - catégorie
# - sous-catégorie
# - localisation
# - prix minimum
# - prix maximum
# - date de service
# - type de contrat


class JobSearchView(generics.ListAPIView):
    serializer_class = JobOfferSerializer
    permission_classes = [AllowAny]
    pagination_class = JobPagination

    def get_queryset(self):
        queryset = JobOffer.objects.filter(is_filled=False)

        # Recherche globale avec ?query
        query = self.request.query_params.get("query")
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(sub_category__name__icontains=query)
            )

        # Filtres supplémentaires
        # Filtrage exact basé sur le nom de la catégorie
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__name__iexact=category)

        # Filtrage exact basé sur le nom de la sous-catégorie
        sub_category = self.request.query_params.get("sub_category")
        if sub_category:
            queryset = queryset.filter(sub_category__name__iexact=sub_category)

        # Recherche partielle par localisation
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location__icontains=location)

        # Filtrer les jobs dont le prix est supérieur ou égal au minimum spécifié
        min_price = self.request.query_params.get("min_price")
        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        # Filtrer les jobs dont le prix est inférieur ou égal au maximum spécifié
        max_price = self.request.query_params.get("max_price")
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        # Filtrer les jobs pour une date de service exacte
        service_date = self.request.query_params.get("service_date")
        if service_date:
            queryset = queryset.filter(service_date=service_date)

        # Filtrer les jobs par type de contrat
        type = self.request.query_params.get("type")
        if type:
            queryset = queryset.filter(type__iexact=type)

        # Retourne le queryset filtré
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            self.add_custom_fields(serializer.data, request.user)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        self.add_custom_fields(serializer.data, request.user)
        return Response(serializer.data)

    def add_custom_fields(self, data_list, user):
        """
        Ajoute les champs personnalisés `status`, `is_favorite`,
        `applicant_count` et `applicants` aux données de chaque offre.
        """
        # Précharger les relations nécessaires
        job_offer_ids = [data["id"] for data in data_list]
        job_offers = JobOffer.objects.filter(id__in=job_offer_ids).prefetch_related(
            "job_favorites",  # Pour les favoris
            "applications__worker__user",  # Pour les candidatures
            "job",  # Pour vérifier le statut de l'offre
        )

        # Créer un dictionnaire pour un accès rapide
        job_offer_dict = {job.id: job for job in job_offers}

        for data in data_list:
            job_offer = job_offer_dict.get(data["id"])
            if not job_offer:
                continue

            # Déterminer le statut de l'offre
            if Job.objects.filter(job_offer=job_offer, worker__user=user).exists():
                data["status"] = "in_progress"
            elif JobApplication.objects.filter(
                job_offer=job_offer, worker__user=user
            ).exists():
                data["status"] = "applied"
            elif Job.objects.filter(job_offer=job_offer, completed=True).exists():
                data["status"] = "completed"
            else:
                data["status"] = None

            # Ajouter les informations supplémentaires
            data["is_favorite"] = job_offer.job_favorites.filter(user=user).exists()
            data["applicant_count"] = job_offer.applications.count()
            # Je veux un try catch pour éviter les erreurs si le worker n'a pas de profile_picture
            data["applicants"] = []
            for app in job_offer.applications.all():
                try:
                    profile_picture = (
                        str(app.worker.user.profile_picture)
                        if app.worker.user.profile_picture
                        else None
                    )
                    picture_url = (
                        str(app.worker.user.picture_url)
                        if hasattr(app.worker.user, "picture_url")
                        else None
                    )
                except (UnicodeDecodeError, AttributeError):
                    profile_picture = None
                    picture_url = None

                data["applicants"].append(
                    {
                        "id": app.worker.user.id,
                        "first_name": app.worker.user.first_name,
                        "last_name": app.worker.user.last_name,
                        "email": app.worker.user.email,
                        "phone_number": app.worker.user.phone_number,
                        "profile_picture": profile_picture,
                        "picture_url": picture_url,
                    }
                )


# JobFavorite Toggle
class HandleJobFavoriteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        job_offer_id = kwargs.get("job_offer_id")
        try:
            job_offer = JobOffer.objects.get(id=job_offer_id)
        except JobOffer.DoesNotExist:
            return Response(
                {"error": "Job offer not found."}, status=status.HTTP_404_NOT_FOUND
            )

        user = request.user
        favorite, created = JobFavorite.objects.get_or_create(
            user=user, job_offer=job_offer
        )

        if not created:
            # Si l'offre est déjà favorite, on la retire
            favorite.delete()
            return Response(
                {"message": "Job offer removed from favorites."},
                status=status.HTTP_200_OK,
            )

        # Si l'offre n'était pas favorite, on l'ajoute
        return Response(
            {"message": "Job offer added to favorites successfully."},
            status=status.HTTP_201_CREATED,
        )
