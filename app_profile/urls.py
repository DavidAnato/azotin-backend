from django.urls import path

from .views import (
    ClientProfileDetailView,
    ClientProfileListCreateView,
    WorkerProfileDetailView,
    WorkerProfileListCreateView,
)

urlpatterns = [
    path(
        "worker-profile/",
        WorkerProfileListCreateView.as_view(),
        name="worker-profile-list-create",
    ),
    path(
        "worker-profile/<int:pk>/",
        WorkerProfileDetailView.as_view(),
        name="worker-profile-detail",
    ),
    path(
        "client-profile/",
        ClientProfileListCreateView.as_view(),
        name="client-profile-list-create",
    ),
    path(
        "client-profile/<int:pk>/",
        ClientProfileDetailView.as_view(),
        name="client-profile-detail",
    ),
]
