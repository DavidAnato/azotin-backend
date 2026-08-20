from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="worker_profile",
        null=True,
        blank=True,
    )
    title = models.ForeignKey(
        "app_job.SubCategory", on_delete=models.CASCADE, blank=True, null=True
    )
    job_types = models.ManyToManyField(
        "app_job.SubCategory",
        related_name="worker_profiles_job_types",
        blank=True,
        help_text="Types de jobs (multi-sélection).",
    )
    # Category
    category = models.ForeignKey(
        "app_job.Category",
        on_delete=models.CASCADE,
        related_name="worker_profiles",
        null=True,
        blank=True,
    )

    skills = models.TextField(max_length=500, blank=True)
    experience = models.IntegerField(default=0, help_text="Years of experience")
    price = models.DecimalField(max_digits=6, decimal_places=0, blank=True, null=True)
    frequency = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("hour", "Hour"),
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
        ],
        help_text="Frequency of the job.",
        default="hour",
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

    def save(self, *args, **kwargs):
        # Assigner automatiquement la catégorie à partir de la sous-catégorie
        if self.title and self.title.category:
            self.category = self.title.category
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profile of {self.user.first_name} {self.user.last_name}"


class PreviousWorkPhoto(models.Model):
    worker_profile = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="previous_work_photos",
        null=True,
        blank=True,
    )
    photo = models.ImageField(upload_to="worker_photos/", blank=True, null=True)

    def __str__(self):
        return f"Photo of {self.worker_profile.user.first_name} {self.worker_profile.user.last_name}"


class ClientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="client_profile",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        "app_job.Category",
        on_delete=models.CASCADE,
        related_name="client_profiles",
        null=True,
        blank=True,
    )
    preferred_payment_method = models.CharField(max_length=50, blank=True)
    average_spent = models.DecimalField(
        max_digits=10, decimal_places=0, blank=True, null=True
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

    def __str__(self):
        return f"Client profile of {self.user.first_name} {self.user.last_name}"


class FavoriteWorker(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="favorite_workers",
        null=True,
        blank=True,
    )
    worker_profile = models.ForeignKey(
        WorkerProfile,
        on_delete=models.CASCADE,
        related_name="favorite_workers",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Favorite for {self.user.first_name} for {self.worker_profile}"
