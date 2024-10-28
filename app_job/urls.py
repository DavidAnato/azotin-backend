from django.urls import path
from .views import JobOfferListCreateView, JobOfferDetailView, JobApplicationListCreateView, JobApplicationDetailView, JobCreateView, JobDetailView

urlpatterns = [
    # Job Offers
    path('job-offers/', JobOfferListCreateView.as_view(), name='job-offer-list-create'),
    path('job-offers/<int:pk>/', JobOfferDetailView.as_view(), name='job-offer-detail'),

    # Job Applications
    path('job-offers/<int:job_offer_id>/applications/', JobApplicationListCreateView.as_view(), name='job-application-list-create'),
    path('job-applications/<int:pk>/', JobApplicationDetailView.as_view(), name='job-application-detail'),

    # Job creation and details
    path('job-applications/<int:job_application_id>/create-job/', JobCreateView.as_view(), name='job-create'),
    path('jobs/<int:pk>/', JobDetailView.as_view(), name='job-detail'),
]
