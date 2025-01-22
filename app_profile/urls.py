from django.urls import path

from .views import (
    ClientProfileDetailView,
    ClientProfileListCreateView,
    FavoriteWorkerToggleView,
    UpdateWorkerProfileView,
    WorkerProfileDetailView,
    WorkerProfileListCreateView,
    WorkerProfileSuggestionListView,
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
    path(
        "update-user-profile/",
        UpdateWorkerProfileView.as_view(),
        name="update-user-profile",
    ),
    path(
        "worker-profile-suggestion/",
        WorkerProfileSuggestionListView.as_view(),
        name="worker-profile-suggestion",
    ),
    path(
        "favorite-worker/<int:worker_profile_id>/toggle/",
        FavoriteWorkerToggleView.as_view(),
        name="favorite-worker-toggle",
    ),
]
