from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AllNotificationsView,
    ClientProfileViewSet,
    IsUnreadNotificationView,
    JobApplicationViewSet,
    JobOfferViewSet,
    JobStatisticsView,
    JobViewSet,
    MarkAllNotificationsAsReadView,
    MarkNotificationAsReadView,
    UnreadNotificationCountView,
    UserViewSet,
    WorkerProfileViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"worker-profiles", WorkerProfileViewSet)
router.register(r"client-profiles", ClientProfileViewSet)
router.register(r"job-offers", JobOfferViewSet)
router.register(r"job-applications", JobApplicationViewSet)
router.register(r"jobs", JobViewSet, basename="job")

urlpatterns = [
    path("", include(router.urls)),
    path("job-statistics/", JobStatisticsView.as_view(), name="job-statistics"),
    path(
        "unread-notifications-count/",
        UnreadNotificationCountView.as_view(),
        name="unread-notifications",
    ),
    path(
        "is-unread-notification/",
        IsUnreadNotificationView.as_view(),
        name="is-unread-notification",
    ),
    path(
        "all-notifications/", AllNotificationsView.as_view(), name="all-notifications"
    ),
    path(
        "mark-notification-as-read/",
        MarkNotificationAsReadView.as_view(),
        name="mark-notification-as-read",
    ),
    path(
        "mark-all-notifications-as-read/",
        MarkAllNotificationsAsReadView.as_view(),
        name="mark-all-notifications-as-read",
    ),
    # path('yearly-statistics/', YearlyStatisticsView.as_view(), name='yearly-statistics'),
    # path('monthly-statistics/', MonthlyStatisticsView.as_view(), name='monthly-statistics'),
    # path('weekly-statistics/', WeeklyStatisticsView.as_view(), name='weekly-statistics'),
    # path('daily-statistics/', DailyStatisticsView.as_view(), name='daily-statistics'),
    # path('data-statistics/', DataStatisticsView.as_view(), name='data-statistics'),
]
