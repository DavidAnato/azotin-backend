from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserNotification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        return UserNotification.objects.filter(recipient=self.request.user).order_by(
            "-created_at"
        )


class MarkNotificationAsReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        try:
            notification = UserNotification.objects.get(
                id=notification_id, recipient=request.user
            )
            notification.is_read = True
            notification.save()
            return Response(
                {"message": "Notification marquée comme lue"}, status=status.HTTP_200_OK
            )
        except UserNotification.DoesNotExist:
            return Response(
                {"error": "Notification non trouvée"}, status=status.HTTP_404_NOT_FOUND
            )


class MarkAllNotificationsAsReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        UserNotification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        return Response(
            {"message": "Toutes les notifications ont été marquées comme lues"},
            status=status.HTTP_200_OK,
        )
