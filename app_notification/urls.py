from django.urls import path

from .views import (
    MarkAllNotificationsAsReadAPIView,
    MarkNotificationAsReadAPIView,
    NotificationListAPIView,
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
]
