from django.urls import path

from .views import (
    AskToMarkAsCompletedView,
    CategoryAndSubCategoryListView,
    CheckPaidServiceView,
    ClientJobStatisticsView,
    HandleJobFavoriteView,
    JobApplicationDetailView,
    JobApplicationListCreateView,
    JobCreateView,
    JobDetailView,
    JobHistoryListView,
    JobOfferDetailView,
    JobOfferListCreateView,
    JobOfferSuggestionListView,
    JobSearchView,
    MarkAsCompletedView,
)

urlpatterns = [
    # Job Offers
    path("job-offers/", JobOfferListCreateView.as_view(), name="job-offer-list-create"),
    path(
        "job-offers/<int:pk>/",
        JobOfferDetailView.as_view(),
        name="job-offer-detail",
    ),
    # Job Applications
    path(
        "job-offers/<int:job_offer_id>/applications/",
        JobApplicationListCreateView.as_view(),
        name="job-application-list-create",
    ),
    path(
        "job-applications/<int:pk>/",
        JobApplicationDetailView.as_view(),
        name="job-application-detail",
    ),
    # Job creation and details
    path(
        "job-applications/<int:job_application_id>/create-job/",
        JobCreateView.as_view(),
        name="job-create",
    ),
    path("jobs/<int:pk>/", JobDetailView.as_view(), name="job-detail"),
    path(
        "job-offers/favorites/<int:job_offer_id>/toggle/",
        HandleJobFavoriteView.as_view(),
        name="job-offer-favorite-toggle",
    ),
    # Job History
    path("job-history/", JobHistoryListView.as_view(), name="job-history-list"),
    # Job Suggestion
    path(
        "job-suggestions/",
        JobOfferSuggestionListView.as_view(),
        name="job-offer-suggestion-list",
    ),
    # Job Search
    path("job-search/", JobSearchView.as_view(), name="job-search"),
    # Category and SubCategory
    path(
        "categories-and-subcategories/",
        CategoryAndSubCategoryListView.as_view(),
        name="category-and-subcategory-list",
    ),
    # Client Job Statistics
    path(
        "client-job-statistics/",
        ClientJobStatisticsView.as_view(),
        name="client-job-statistics",
    ),
    path(
        "ask-complete/<int:job_offer_id>/",
        AskToMarkAsCompletedView.as_view(),
        name="ask-complete-job",
    ),
    path(
        "mark-completed/<int:job_offer_id>/",
        MarkAsCompletedView.as_view(),
        name="mark-job-completed",
    ),
    path(
        "check-paid-service/",
        CheckPaidServiceView.as_view(),
        name="check-paid-service",
    ),
]
