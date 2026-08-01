from django.contrib.auth import get_user_model
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from .models import NotificationToken, UserNotification
from .serializers import NotificationTokenSerializer, UserNotificationSerializer
from .sse import sse_event_generator

User = get_user_model()


class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListAPIView(generics.ListAPIView):
    serializer_class = UserNotificationSerializer
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


class NotificationTokenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")

        # Vérifier si le token existe déjà
        existing_token = NotificationToken.objects.filter(token=token).first()
        if existing_token:
            serializer = NotificationTokenSerializer(existing_token)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = NotificationTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DeleteNotificationTokenAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        token = request.query_params.get("token")
        NotificationToken.objects.filter(token=token, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _authenticate_bearer(request):
    """Auth JWT hors DRF (évite le 406 sur Accept: text/event-stream)."""
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return None
    raw = header[7:].strip()
    if not raw:
        return None
    try:
        access = AccessToken(raw)
        return User.objects.get(pk=access["user_id"], is_active=True)
    except Exception:
        return None


@method_decorator(csrf_exempt, name="dispatch")
class NotificationStreamAPIView(View):
    """Flux SSE des notifications utilisateur (JWT Bearer)."""

    def get(self, request):
        user = _authenticate_bearer(request)
        if user is None:
            return HttpResponse(
                b'{"detail":"Authentication credentials were not provided."}',
                status=401,
                content_type="application/json",
            )

        response = StreamingHttpResponse(
            sse_event_generator(user.id),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        response["Connection"] = "keep-alive"
        return response
