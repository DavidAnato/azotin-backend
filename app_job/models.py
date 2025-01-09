from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="subcategories"
    )

    def __str__(self):
        return self.name


class JobOffer(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="job_offers"
    )
    sub_category = models.ForeignKey(
        SubCategory, on_delete=models.CASCADE, related_name="job_offers"
    )
    client = models.ForeignKey("app_profile.ClientProfile", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to="job_offers/", null=True, blank=True)
    description = models.TextField()
    responsability = models.TextField()
    location = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=9, decimal_places=2, help_text="Minimum price for the job."
    )
    service_date = models.DateTimeField(
        null=True, blank=True, help_text="Scheduled date and time for the service."
    )
    is_recurring = models.BooleanField(
        default=False, help_text="True if the service is recurring."
    )
    type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("full_time", "Full Time"),
            ("part_time", "Part Time"),
            ("contract", "Contract"),
            ("other", "Other"),
        ],
        help_text="Type of the job.",
    )
    recurrence_frequency = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("biweekly", "Biweekly"),
            ("monthly", "Monthly"),
        ],
        help_text="Applicable if the service is recurring.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_filled = models.BooleanField(
        default=False, help_text="True once a worker is selected."
    )
    location_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Latitude of the job location.",
    )
    location_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text="Longitude of the job location.",
    )

    def __str__(self):
        return f"Job offer by {self.client.user.first_name} at {self.location}"


class JobApplication(models.Model):
    job_offer = models.ForeignKey(
        JobOffer, on_delete=models.CASCADE, related_name="applications"
    )
    worker = models.ForeignKey(
        "app_profile.WorkerProfile",
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    proposed_price = models.DecimalField(max_digits=9, decimal_places=2)
    cover_letter = models.TextField(
        blank=True, help_text="Optional cover letter by the worker."
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Application by {self.worker.user.first_name} for {self.job_offer}"


class Job(models.Model):
    job_offer = models.OneToOneField(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="job",
        help_text="The related job offer.",
    )
    client = models.ForeignKey(
        "app_profile.ClientProfile",
        on_delete=models.CASCADE,
        related_name="assigned_jobs",
    )
    worker = models.ForeignKey(
        "app_profile.WorkerProfile",
        on_delete=models.CASCADE,
        related_name="assigned_jobs",
    )
    description = models.TextField()
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=9, decimal_places=2)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job for {self.client.user.first_name} by {self.worker.user.first_name}"


class JobFavorite(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="job_favorites"
    )
    job_offer = models.ForeignKey(
        JobOffer, on_delete=models.CASCADE, related_name="job_favorites"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Favorite for {self.user.first_name} for {self.job_offer}"
