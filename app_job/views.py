from django.contrib.auth import get_user_model
from django.contrib.gis.measure import D
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
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


# Category Views
class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class SubCategoryListView(generics.ListAPIView):
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer


class JobOfferListCreateView(generics.ListCreateAPIView):
    queryset = JobOffer.objects.all().order_by("-created_at")
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

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
        for data in data_list:
            job_offer = JobOffer.objects.get(pk=data["id"])
            # Statut de l'offre
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

            # Offre favorite
            data["is_favorite"] = JobFavorite.objects.filter(
                user=user, job_offer=job_offer
            ).exists()

            # Nombre de candidatures
            data["applicant_count"] = JobApplication.objects.filter(
                job_offer=job_offer
            ).count()

            # Liste des candidats
            data["applicants"] = [
                {
                    "id": app.worker.user.id,
                    "first_name": app.worker.user.first_name,
                    "last_name": app.worker.user.last_name,
                    "email": app.worker.user.email,
                    "phone_number": app.worker.user.phone_number,
                    "profile_picture": (
                        app.worker.user.profile_picture
                        if app.worker.user.profile_picture
                        else None
                    ),
                    "picture_url": app.worker.user.picture_url,
                }
                for app in JobApplication.objects.filter(job_offer=job_offer)
            ]

    def perform_create(self, serializer):
        client_profile = ClientProfile.objects.get(user=self.request.user)
        serializer.save(client=client_profile)


class JobOfferDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View to retrieve, update, or delete a Job Offer.
    - Anyone can view the jobs.
    - Only the owner (client) can update or delete their jobs.
    """

    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        job_offer = super().get_object()

        # Restrict write permissions to the owner of the job
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            if job_offer.client.user != self.request.user:
                raise PermissionDenied(
                    "You are not allowed to modify or delete this Job Offer."
                )

        return job_offer


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


# Job Favorite Views
class JobOfferFavoriteListView(generics.ListAPIView):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        return JobOffer.objects.filter(job_favorites__user=self.request.user)


# l'historique des emplois
class JobHistoryListView(generics.ListAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        # Essayer de récupérer le profil WorkerProfile associé à l'utilisateur connecté
        worker_profile, created = WorkerProfile.objects.get_or_create(
            user=self.request.user
        )

        if created:
            # Si le profil a été créé, tu peux également envoyer un message d'info si nécessaire
            print(f"WorkerProfile for user {self.request.user} has been created.")

        return Job.objects.filter(worker=worker_profile)


# emplois suggérés
class JobOfferSuggestionListView(generics.ListAPIView):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        if self.request.user.category:
            return JobOffer.objects.filter(
                category=self.request.user.category,
                location__distance_lte=(self.request.user.location, D(km=10)),
            )
        else:
            return JobOffer.objects.all()


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
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        queryset = JobOffer.objects.all()

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
        contract_type = self.request.query_params.get("contract_type")
        if contract_type:
            queryset = queryset.filter(contract_type__iexact=contract_type)

        # Retourne le queryset filtré
        return queryset


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
