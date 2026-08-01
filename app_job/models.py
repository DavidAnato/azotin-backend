from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name


class JobOffer(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="job_offers",
        null=True,
        blank=True,
    )
    sub_category = models.ForeignKey(
        SubCategory,
        on_delete=models.CASCADE,
        related_name="job_offers",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "app_profile.ClientProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to="job_offers/", null=True, blank=True)
    voice_note = models.FileField(
        upload_to="job_offers/voice/",
        null=True,
        blank=True,
        help_text="Note vocale décrivant la mission (alternative au texte).",
    )
    description = models.TextField(blank=True, default="")
    responsability = models.TextField(blank=True, default="")
    location = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=9, decimal_places=0, help_text="Minimum price for the job."
    )
    frequency = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("hour", "Hour"),
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("fixed", "Fixed / forfait"),
        ],
        help_text="Frequency of the job.",
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

    def save(self, *args, **kwargs):
        # Assigner automatiquement la catégorie à partir de la sous-catégorie
        if self.sub_category and self.sub_category.category:
            self.category = self.sub_category.category
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} by {self.client.user.first_name} at {self.location}"


class JobApplication(models.Model):
    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="applications",
        null=True,
    )
    worker = models.ForeignKey(
        "app_profile.WorkerProfile",
        on_delete=models.CASCADE,
        related_name="job_applications",
        null=True,
    )
    proposed_price = models.DecimalField(max_digits=9, decimal_places=0)
    frequency = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("hour", "Hour"),
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("fixed", "Fixed / forfait"),
        ],
        help_text="Frequency of the job.",
    )
    cover_letter = models.TextField(
        blank=True, help_text="Optional cover letter by the worker."
    )
    voice_note = models.FileField(
        upload_to="job_applications/voice/",
        null=True,
        blank=True,
        help_text="Note vocale de candidature (alternative au texte).",
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
        null=True,
    )
    client = models.ForeignKey(
        "app_profile.ClientProfile",
        on_delete=models.CASCADE,
        related_name="assigned_jobs",
        null=True,
        blank=True,
    )
    worker = models.ForeignKey(
        "app_profile.WorkerProfile",
        on_delete=models.CASCADE,
        related_name="assigned_jobs",
        null=True,
    )
    description = models.TextField()
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=9, decimal_places=0)
    frequency = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("hour", "Hour"),
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("fixed", "Fixed / forfait"),
        ],
        help_text="Frequency of the job.",
    )
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job for {self.client.user.first_name} by {self.worker.user.first_name}"


class JobFavorite(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="job_favorites",
        null=True,
    )
    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name="job_favorites",
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Favorite for {self.user.first_name} for {self.job_offer}"


class PaidService(models.Model):
    is_job_offer_paid = models.BooleanField(default=False)
    is_job_offer_paid_price = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True
    )
    is_job_application_paid = models.BooleanField(default=False)
    is_job_application_paid_price = models.DecimalField(
        max_digits=10, decimal_places=0, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if not self.pk and PaidService.objects.exists():
            raise ValidationError("Il existe déjà un objet PaidService.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return "Configuration des services payants"

    class Meta:
        verbose_name = "Service Payant"
        verbose_name_plural = "Service Payant"
