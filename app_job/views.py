from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from app_profile.models import ClientProfile, WorkerProfile
from .models import JobOffer, JobApplication, Job
from .serializers import JobOfferSerializer, JobApplicationSerializer, JobSerializer
from rest_framework.exceptions import PermissionDenied


### Job Offer Views
class JobOfferListCreateView(generics.ListCreateAPIView):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        client_profile = ClientProfile.objects.get(user=self.request.user)
        serializer.save(client=client_profile)

class JobOfferDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobOffer.objects.all()
    serializer_class = JobOfferSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        job_offer = super().get_object()
        if job_offer.client.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this Job Offer.")
        return job_offer

### Job Application Views
class JobApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return JobApplication.objects.filter(job_offer__id=self.kwargs['job_offer_id'])

    def perform_create(self, serializer):
        worker_profile = WorkerProfile.objects.get(user=self.request.user)
        job_offer = JobOffer.objects.get(id=self.kwargs['job_offer_id'])
        if job_offer.is_filled:
            raise PermissionDenied("This job offer is already filled.")
        serializer.save(worker=worker_profile, job_offer=job_offer)

class JobApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobApplication.objects.all()
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        job_application = super().get_object()
        if job_application.worker.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this Job Application.")
        return job_application

### Job Creation and Detail Views
class JobCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_application_id):
        job_application = JobApplication.objects.get(id=job_application_id)
        if job_application.job_offer.client.user != request.user:
            raise PermissionDenied("You are not allowed to create a job from this application.")
        if job_application.status != 'pending':
            return Response({"detail": "This application has already been processed."}, status=status.HTTP_400_BAD_REQUEST)
        
        job_application.status = 'accepted'
        job_application.save()

        # Mark the job offer as filled
        job_application.job_offer.is_filled = True
        job_application.job_offer.save()

        # Create the Job instance
        job = Job.objects.create(
            job_offer=job_application.job_offer,
            client=job_application.job_offer.client,
            worker=job_application.worker,
            description=job_application.job_offer.description,
            location=job_application.job_offer.location,
            price=job_application.proposed_price
        )

        serializer = JobSerializer(job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        job = super().get_object()
        if job.client.user != self.request.user and job.worker.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this job.")
        return job
