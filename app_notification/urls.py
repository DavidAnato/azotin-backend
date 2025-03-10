from django.urls import path

from .views import (
    DeleteNotificationTokenAPIView,
    MarkAllNotificationsAsReadAPIView,
    MarkNotificationAsReadAPIView,
    NotificationListAPIView,
    NotificationTokenAPIView,
)

urlpatterns = [
    path(
        "user-notifications/",
        NotificationListAPIView.as_view(),
        name="notification-list",
    ),
    path(
        "mark-notification-as-read/<int:notification_id>/",
        MarkNotificationAsReadAPIView.as_view(),
        name="mark-notification-as-read",
    ),
    path(
        "mark-all-notifications-as-read/",
        MarkAllNotificationsAsReadAPIView.as_view(),
        name="mark-all-notifications-as-read",
    ),
    path(
        "create-token/",
        NotificationTokenAPIView.as_view(),
        name="create-token",
    ),
    path(
        "delete-token/",
        DeleteNotificationTokenAPIView.as_view(),
        name="delete-token",
    ),
]
