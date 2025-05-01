from django.contrib.auth import get_user_model
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from app_job.models import Job, JobApplication, JobOffer
from app_job.serializers import (
    JobApplicationSerializer,
    JobOfferSerializer,
    JobSerializer,
)
from app_profile.models import ClientProfile, WorkerProfile
from app_profile.serializers import ClientProfileSerializer, WorkerProfileSerializer
from authentication.serializers import UserSerializer

from .models import BackofficeNotification
from .serializers import BackofficeNotificationSerializer, JobStatisticsSerializer

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 4
    page_size_query_param = "page_size"
    max_page_size = 100


class BaseViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    # permission_classes = [permissions.IsAdminUser | permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]
    ordering = ["-id"]  # Default ordering by most recent


class UserViewSet(BaseViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    search_fields = ["username", "email"]
    ordering_fields = ["username", "email", "date_joined"]


class WorkerProfileViewSet(BaseViewSet):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    search_fields = ["user__username", "user__email", "profession"]
    ordering_fields = ["user__username", "user__email", "profession"]


class ClientProfileViewSet(BaseViewSet):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    search_fields = ["user__username", "user__email", "company_name"]
    ordering_fields = ["user__username", "user__email", "company_name"]


class JobOfferViewSet(BaseViewSet):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    search_fields = ["title", "description", "location"]
    ordering_fields = ["title", "created_at", "location"]


class JobApplicationViewSet(BaseViewSet):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    search_fields = ["job__title", "applicant__username", "status"]
    ordering_fields = ["job__title", "applicant__username", "status"]


class JobViewSet(BaseViewSet):
    serializer_class = JobSerializer
    search_fields = ["title", "description"]
    ordering_fields = ["title", "created_at"]

    def get_queryset(self):
        queryset = Job.objects.all()
        is_completed = self.request.query_params.get("is_completed")
        if is_completed is not None:
            queryset = queryset.filter(completed=is_completed)
        return queryset


# Notifications
class UnreadNotificationCountView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BackofficeNotificationSerializer  # Ajouté

    def get(self, request, *args, **kwargs):
        user = request.user
        unread_count = BackofficeNotification.objects.exclude(
            users_read__id=user.id
        ).count()  # Corrected
        return Response({"unread_count": unread_count})


class IsUnreadNotificationView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BackofficeNotificationSerializer  # Ajouté

    def get(self, request, *args, **kwargs):
        user = request.user
        user_notification_unread = (
            BackofficeNotification.objects.filter(notification_type="user_notification")
            .exclude(users_read__id=user.id)
            .exists()
        )  # Corrected
        news_notification_unread = (
            BackofficeNotification.objects.filter(notification_type="news_notification")
            .exclude(users_read__id=user.id)
            .exists()
        )  # Corrected
        system_notification_unread = (
            BackofficeNotification.objects.filter(
                notification_type="system_notification"
            )
            .exclude(users_read__id=user.id)
            .exists()
        )  # Corrected

        return Response(
            {
                "user_notification_unread": user_notification_unread,
                "news_notification_unread": news_notification_unread,
                "system_notification_unread": system_notification_unread,
            }
        )


class AllNotificationsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BackofficeNotificationSerializer  # Ajouté
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        nb_start = self.request.query_params.get("nb_start")
        nb_end = self.request.query_params.get("nb_end")
        if nb_start is not None and nb_end is not None:
            try:
                nb_start = int(nb_start)
                nb_end = int(nb_end)
                return BackofficeNotification.objects.all().order_by("-created_at")[
                    nb_start:nb_end
                ]  # Retrieve the specified number of notifications
            except ValueError:
                return BackofficeNotification.objects.none()
        else:
            return BackofficeNotification.objects.all().order_by(
                "-created_at"
            )  # Retrieve all notifications ordered from most recent to oldest


class MarkNotificationAsReadView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BackofficeNotificationSerializer  # Ajouté

    def post(self, request, *args, **kwargs):
        user = request.user
        notification_id = request.data.get("notification_id")
        if not notification_id:
            return Response(
                {"error": "Notification ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            notification = BackofficeNotification.objects.get(id=notification_id)
        except BackofficeNotification.DoesNotExist:
            return Response(
                {"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
            )

        notification.users_read.add(user)
        notification.save()

        return Response(
            {"message": "Notification marked as read"}, status=status.HTTP_200_OK
        )


class MarkAllNotificationsAsReadView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BackofficeNotificationSerializer  # Ajouté

    def post(self, request, *args, **kwargs):
        user = request.user
        notifications = BackofficeNotification.objects.exclude(users_read__id=user.id)
        for notification in notifications:
            notification.users_read.add(user)
            notification.save()

        return Response(
            {"message": "All notifications marked as read"}, status=status.HTTP_200_OK
        )


class JobStatisticsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = JobStatisticsSerializer

    def get(self, request, *args, **kwargs):
        job_offer_count = JobOffer.objects.count()
        job_application_count = JobApplication.objects.count()
        job_progress_count = Job.objects.filter(completed=False).count()
        job_completed_count = Job.objects.filter(completed=True).count()

        data = {
            "job_offer_count": job_offer_count,
            "job_application_count": job_application_count,
            "job_progress_count": job_progress_count,
            "job_completed_count": job_completed_count,
        }

        serializer = self.serializer_class(data=data)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
