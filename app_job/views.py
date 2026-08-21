# from math import atan2, cos, radians, sin, sqrt

from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Case, IntegerField, Q, When
from django.forms import ValidationError
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app_notification.utils import create_user_notification
from app_profile.models import ClientProfile, WorkerProfile
from authentication.kyc import kyc_block_if_needed

from .models import (
    Category,
    Job,
    JobApplication,
    JobFavorite,
    JobOffer,
    PaidService,
    SubCategory,
)
from .search import (
    JOB_OFFER_SEARCH_FIELDS,
    compute_match_score,
    expand_search_query,
    has_only_urgency_keywords,
    has_urgency_intent,
    keywords_to_q,
)
from .serializers import (
    CategorySerializer,
    JobApplicationSerializer,
    JobOfferSerializer,
    JobSerializer,
    PaidServiceSerializer,
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

    def create(self, request, *args, **kwargs):
        blocked = kyc_block_if_needed(request.user)
        if blocked is not None:
            return blocked
        return super().create(request, *args, **kwargs)


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
        queryset = JobApplication.objects.filter(
            job_offer__id=self.kwargs["job_offer_id"]
        )
        accepted = self.request.query_params.get("accepted", None)
        if accepted == "true":
            queryset = queryset.filter(status="accepted")
        return queryset

    def perform_create(self, serializer):
        job_offer = JobOffer.objects.get(id=self.kwargs["job_offer_id"])
        if job_offer.is_filled:
            raise PermissionDenied("Cette offre est déjà pourvue.")
        try:
            worker_profile = WorkerProfile.objects.get(user=self.request.user)
        except WorkerProfile.DoesNotExist:
            raise PermissionDenied(
                "Seuls les travailleurs peuvent postuler à une offre."
            )
        if JobApplication.objects.filter(
            worker=worker_profile, job_offer=job_offer
        ).exists():
            raise PermissionDenied("Vous avez déjà postulé à cette offre.")
        serializer.save(worker=worker_profile, job_offer=job_offer)

    def create(self, request, *args, **kwargs):
        blocked = kyc_block_if_needed(request.user)
        if blocked is not None:
            return blocked
        return super().create(request, *args, **kwargs)


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

        offer = job_application.job_offer
        title = (offer.title or "").strip() or f"Mission - offre #{offer.pk}"

        with transaction.atomic():
            job = Job.objects.create(
                job_offer=offer,
                client=offer.client,
                worker=job_application.worker,
                description=offer.description,
                location=offer.location,
                price=job_application.proposed_price,
                frequency=offer.frequency,
            )

            # Contrat escrow lié au job (créé à l'acceptation du candidat)
            from app_escrow.models import Contract, ContractStatus

            Contract.objects.create(
                client=request.user,
                freelancer=job_application.worker.user,
                job_offer=offer,
                job=job,
                title=title,
                description=offer.description or title,
                amount=job_application.proposed_price,
                currency="XOF",
                status=ContractStatus.ACCEPTED,
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
                    sub_category=worker_profile.title,
                    is_filled=False,
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
# - query (title, description, responsabilité, catégorie, sous-catégorie, lieu)
#   expansion synonymes / mots-clés via app_job.search
# Filtres :
# - catégorie, sous-catégorie, localisation, prix, type de contrat
# - date de service, échéance (deadline), urgent (is_urgent)
class JobSearchView(generics.ListAPIView):
    serializer_class = JobOfferSerializer
    permission_classes = [AllowAny]
    pagination_class = JobPagination

    @staticmethod
    def _parse_date_param(value):
        if value is None or str(value).strip() == "":
            return None
        raw = str(value).strip()[:10]
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_bool_param(value):
        if value is None or str(value).strip() == "":
            return None
        token = str(value).strip().lower()
        if token in ("1", "true", "yes", "oui"):
            return True
        if token in ("0", "false", "no", "non"):
            return False
        return None

    def get_queryset(self):
        queryset = (
            JobOffer.objects.filter(is_filled=False)
            .select_related("category", "sub_category")
            .order_by("-is_urgent", "-created_at")
        )

        # Recherche globale avec ?query (mots-clés OR + expansion synonyme)
        query = self.request.query_params.get("query")
        self._search_keywords = []
        self._urgency_intent = False
        if query and str(query).strip():
            keywords = expand_search_query(query)
            if not keywords:
                keywords = [str(query).strip()]
            self._search_keywords = keywords
            self._urgency_intent = has_urgency_intent(keywords)
            q_objects = keywords_to_q(keywords, JOB_OFFER_SEARCH_FIELDS)
            if has_only_urgency_keywords(str(query).replace(",", " ").split()):
                q_objects |= Q(is_urgent=True)
            queryset = queryset.filter(q_objects).distinct()

        # Filtres supplémentaires
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__name__iexact=category)

        sub_category = self.request.query_params.get("sub_category")
        if sub_category:
            queryset = queryset.filter(sub_category__name__iexact=sub_category)

        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location__icontains=location)

        price_frequency = self.request.query_params.get("price_frequency", "hour")

        min_price = self.request.query_params.get("min_price")
        if min_price:
            min_price_converted = self.convert_price(
                float(min_price), price_frequency, "hour"
            )
            queryset = queryset.filter(price__gte=min_price_converted)

        max_price = self.request.query_params.get("max_price")
        if max_price:
            max_price_converted = self.convert_price(
                float(max_price), price_frequency, "hour"
            )
            queryset = queryset.filter(price__lte=max_price_converted)

        service_date = self._parse_date_param(
            self.request.query_params.get("service_date")
        )
        if service_date:
            queryset = queryset.filter(service_date__date=service_date)

        service_date_from = self._parse_date_param(
            self.request.query_params.get("service_date_from")
        )
        if service_date_from:
            queryset = queryset.filter(service_date__date__gte=service_date_from)

        service_date_to = self._parse_date_param(
            self.request.query_params.get("service_date_to")
        )
        if service_date_to:
            queryset = queryset.filter(service_date__date__lte=service_date_to)

        params = self.request.query_params
        deadline_exact = self._parse_date_param(params.get("deadline"))
        if deadline_exact:
            queryset = queryset.filter(deadline=deadline_exact)

        deadline_before = self._parse_date_param(
            params.get("deadline_before") or params.get("deadline_to")
        )
        if deadline_before:
            queryset = queryset.filter(deadline__lte=deadline_before)

        deadline_after = self._parse_date_param(
            params.get("deadline_after") or params.get("deadline_from")
        )
        if deadline_after:
            queryset = queryset.filter(deadline__gte=deadline_after)

        urgent = self._parse_bool_param(
            params.get("urgent")
            if params.get("urgent") not in (None, "")
            else params.get("is_urgent")
        )
        if urgent is True:
            queryset = queryset.filter(is_urgent=True)
        elif urgent is False:
            queryset = queryset.filter(is_urgent=False)

        job_type = self.request.query_params.get("type")
        if job_type:
            queryset = queryset.filter(type__iexact=job_type)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        keywords = getattr(self, "_search_keywords", []) or []
        urgency_intent = getattr(self, "_urgency_intent", False)
        match_scores = {}
        if keywords:
            scored = []
            for offer in queryset:
                score = compute_match_score(
                    offer, keywords, urgency_intent=urgency_intent
                )
                match_scores[offer.id] = score
                deadline = getattr(offer, "deadline", None)
                deadline_ord = deadline.toordinal() if deadline else 10**9
                urgent_rank = 0 if getattr(offer, "is_urgent", False) else 1
                scored.append((score, urgent_rank, deadline_ord, offer.pk))
            scored.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
            pk_order = [pk for _, _, _, pk in scored]
            if pk_order:
                preserved = Case(
                    *[When(pk=pk, then=pos) for pos, pk in enumerate(pk_order)],
                    output_field=IntegerField(),
                )
                queryset = queryset.filter(pk__in=pk_order).order_by(preserved)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            self.add_custom_fields(serializer.data, request.user, match_scores)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        self.add_custom_fields(serializer.data, request.user, match_scores)
        return Response(serializer.data)

    def add_custom_fields(self, data_list, user, match_scores=None):
        match_scores = match_scores or {}
        authenticated = getattr(user, "is_authenticated", False)
        job_offer_ids = [data["id"] for data in data_list]
        job_offers = JobOffer.objects.filter(id__in=job_offer_ids).prefetch_related(
            "job_favorites", "applications__worker__user", "job"
        )

        job_offer_dict = {job.id: job for job in job_offers}

        for data in data_list:
            job_offer = job_offer_dict.get(data["id"])
            if not job_offer:
                continue

            data["match_score"] = match_scores.get(data["id"], 0)

            if not authenticated:
                data["status"] = None
                data["is_favorite"] = False
                data["applicant_count"] = job_offer.applications.count()
                data["applicants"] = []
                continue

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

            data["is_favorite"] = job_offer.job_favorites.filter(user=user).exists()
            data["applicant_count"] = job_offer.applications.count()
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

    @staticmethod
    def convert_price(price, from_frequency, to_frequency):
        if from_frequency == "fixed" or to_frequency == "fixed":
            return price
        conversion_rates = {
            "hour": {"hour": 1, "day": 8, "week": 40, "month": 160},
            "day": {"hour": 1 / 8, "day": 1, "week": 5, "month": 20},
            "week": {"hour": 1 / 40, "day": 1 / 5, "week": 1, "month": 4},
            "month": {"hour": 1 / 160, "day": 1 / 20, "week": 1 / 4, "month": 1},
        }
        try:
            return price * conversion_rates[from_frequency][to_frequency]
        except KeyError:
            return price


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


class ClientJobStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Vérifier que l'utilisateur a un profil client
            if not hasattr(request.user, "client_profile"):
                return Response(
                    {"error": "Profil client non trouvé"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            client_profile = request.user.client_profile

            # Obtenir les statistiques
            jobs_posted = JobOffer.objects.filter(client=client_profile).count()
            jobs_in_progress = Job.objects.filter(
                client=client_profile, completed=False
            ).count()
            jobs_completed = Job.objects.filter(
                client=client_profile, completed=True
            ).count()

            data = {
                "jobs_posted": jobs_posted,
                "jobs_in_progress": jobs_in_progress,
                "jobs_completed": jobs_completed,
            }

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Une erreur est survenue : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WorkerJobStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            if not hasattr(request.user, "worker_profile"):
                return Response(
                    {"error": "Profil travailleur non trouvé"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            worker_profile = request.user.worker_profile
            jobs_in_progress = Job.objects.filter(
                worker=worker_profile, completed=False
            ).count()
            jobs_completed = Job.objects.filter(
                worker=worker_profile, completed=True
            ).count()
            applications_pending = JobApplication.objects.filter(
                worker=worker_profile, status="pending"
            ).count()
            favorites = JobFavorite.objects.filter(user=request.user).count()

            return Response(
                {
                    "jobs_in_progress": jobs_in_progress,
                    "jobs_completed": jobs_completed,
                    "applications_pending": applications_pending,
                    "favorites": favorites,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": f"Une erreur est survenue : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WorkerMyApplicationsListView(generics.ListAPIView):
    """Candidatures du travailleur (offres postulées, pas encore de mission)."""

    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = JobPagination

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, "worker_profile"):
            return JobApplication.objects.none()

        qs = (
            JobApplication.objects.filter(worker=user.worker_profile)
            .select_related(
                "job_offer",
                "job_offer__category",
                "job_offer__sub_category",
                "job_offer__client",
                "job_offer__client__user",
            )
            .order_by("-applied_at")
        )

        # Par défaut : en attente (pas encore acceptée / devenue job)
        status_param = self.request.query_params.get("status", "pending")
        if status_param and status_param != "all":
            qs = qs.filter(status=status_param)
        return qs



class AskToMarkAsCompletedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_offer_id):
        try:
            # Trouver le job associé au job_offer_id
            job = Job.objects.get(job_offer_id=job_offer_id)

            # Vérifier que l'utilisateur est bien le travailleur de ce job
            if job.worker.user != request.user:
                return Response(
                    {"detail": "Vous n'êtes pas autorisé à effectuer cette action."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Créer une notification pour le client
            create_user_notification(
                recipient=job.client.user,
                message=f"{request.user.first_name} {request.user.last_name} "
                f"a demandé de marquer le job '{job.job_offer.title}' comme terminé.",
                object={
                    "type": "ask_complete_job",
                    "job_id": job.id,
                    "job_title": job.job_offer.title,
                    "worker_name": f"{request.user.first_name} {request.user.last_name}",
                },
            )

            return Response(
                {"detail": "Demande envoyée avec succès."}, status=status.HTTP_200_OK
            )

        except Job.DoesNotExist:
            return Response(
                {"detail": "Job non trouvé."}, status=status.HTTP_404_NOT_FOUND
            )


class MarkAsCompletedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_offer_id):
        try:
            # Trouver le job associé au job_offer_id
            job = Job.objects.get(job_offer_id=job_offer_id)

            # Vérifier que l'utilisateur est bien le client de ce job
            if job.client.user != request.user:
                return Response(
                    {"detail": "Vous n'êtes pas autorisé à effectuer cette action."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Marquer le job comme terminé
            job.completed = True
            job.save()

            # Créer une notification pour le travailleur
            create_user_notification(
                recipient=job.worker.user,
                message=f"Le job '{job.job_offer.title}' a été marqué comme terminé par "
                f"{request.user.first_name} {request.user.last_name}.",
                object={
                    "type": "job_completed",
                    "job_id": job.id,
                    "job_title": job.job_offer.title,
                    "client_name": f"{request.user.first_name} {request.user.last_name}",
                },
            )

            return Response(
                {"detail": "Job marqué comme terminé avec succès."},
                status=status.HTTP_200_OK,
            )

        except Job.DoesNotExist:
            return Response(
                {"detail": "Job non trouvé."}, status=status.HTTP_404_NOT_FOUND
            )


class CheckPaidServiceView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaidServiceSerializer

    def get_object(self):
        paid_service = PaidService.objects.first()
        return paid_service
