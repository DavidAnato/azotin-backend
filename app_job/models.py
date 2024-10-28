from app_profile.models import ClientProfile, WorkerProfile
from django.db import models

class JobOffer(models.Model):
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name="job_offers")
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    price_range_min = models.DecimalField(max_digits=9, decimal_places=2, help_text="Minimum price for the job.")
    price_range_max = models.DecimalField(max_digits=9, decimal_places=2, help_text="Maximum price for the job.")
    service_date = models.DateTimeField(null=True, blank=True, help_text="Scheduled date and time for the service.")
    is_recurring = models.BooleanField(default=False, help_text="True if the service is recurring.")
    recurrence_frequency = models.CharField(
        max_length=50, 
        blank=True, 
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('biweekly', 'Biweekly'),
            ('monthly', 'Monthly')
        ], 
        help_text="Applicable if the service is recurring."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_filled = models.BooleanField(default=False, help_text="True once a worker is selected.")

    def __str__(self):
        return f"Job offer by {self.client.user.first_name} at {self.location}"

class JobApplication(models.Model):
    job_offer = models.ForeignKey(JobOffer, on_delete=models.CASCADE, related_name="applications")
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="job_applications")
    proposed_price = models.DecimalField(max_digits=9, decimal_places=2)
    cover_letter = models.TextField(blank=True, help_text="Optional cover letter by the worker.")
    status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected')
        ], 
        default='pending'
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Application by {self.worker.user.first_name} for {self.job_offer}"

class Job(models.Model):
    job_offer = models.OneToOneField(JobOffer, on_delete=models.CASCADE, related_name="job", help_text="The related job offer.")
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name="assigned_jobs")
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name="assigned_jobs")
    description = models.TextField()
    location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=9, decimal_places=2)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Job for {self.client.user.first_name} by {self.worker.user.first_name}"
