from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClientProfile, WorkerProfile
from .serializers import ClientProfileSerializer, WorkerProfileSerializer


### Worker Profile Views
class WorkerProfileListCreateView(generics.ListCreateAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WorkerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        worker_profile = super().get_object()
        if worker_profile.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this Worker Profile.")
        return worker_profile


### Client Profile Views
class ClientProfileListCreateView(generics.ListCreateAPIView):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ClientProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ClientProfile.objects.all()
    serializer_class = ClientProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        client_profile = super().get_object()
        if client_profile.user != self.request.user:
            raise PermissionDenied("You are not allowed to access this Client Profile.")
        return client_profile
