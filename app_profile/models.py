from django.contrib.auth import get_user_model
from django.db import models

from app_job.models import SubCategory

User = get_user_model()


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="worker_profile"
    )
    title = models.ForeignKey(
        SubCategory, on_delete=models.CASCADE, blank=True, null=True
    )
    # Category
    category = models.ForeignKey(
        "app_job.Category",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    skills = models.TextField(max_length=500, blank=True)
    experience = models.IntegerField(default=0, help_text="Years of experience")
    hourly_rate = models.DecimalField(
        max_digits=6, decimal_places=2, blank=True, null=True
    )
    certifications = models.TextField(max_length=500, blank=True)
    available_for_hire = models.BooleanField(default=True)
    total_jobs_completed = models.IntegerField(default=0)

    # Notification Preferences
    new_job_notification = models.BooleanField(default=True)
    new_message_notification = models.BooleanField(default=True)
    new_rejected_notification = models.BooleanField(default=True)
    new_call_notification = models.BooleanField(default=True)
    new_hire_notification = models.BooleanField(default=True)

    def __str__(self):
        return f"Profile of {self.user.first_name} {self.user.last_name}"


class PreviousWorkPhoto(models.Model):
    worker_profile = models.ForeignKey(
        WorkerProfile, on_delete=models.CASCADE, related_name="previous_work_photos"
    )
    photo = models.ImageField(upload_to="worker_photos/", blank=True, null=True)

    def __str__(self):
        return f"Photo of {self.worker_profile.user.first_name} {self.worker_profile.user.last_name}"


class ClientProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="client_profile"
    )
    preferred_payment_method = models.CharField(max_length=50, blank=True)
    total_jobs_posted = models.IntegerField(default=0)
    job_completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="En pourcentage",
    )
    average_spent = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    loyalty_points = models.IntegerField(default=0)
    SERVICE_TYPE_CHOICES = [
        ("home", "Home"),
        ("business", "Business"),
    ]
    service_name = models.CharField(max_length=100, blank=True)
    service_type = models.CharField(
        max_length=10, choices=SERVICE_TYPE_CHOICES, blank=True
    )
    service_description = models.TextField(max_length=1000, blank=True)
    location_description = models.TextField(max_length=1000, blank=True)
    location_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    location_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )

    def __str__(self):
        return f"Client profile of {self.user.first_name} {self.user.last_name}"
