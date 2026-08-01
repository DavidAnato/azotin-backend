from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class BackofficeNotification(models.Model):
    title = models.CharField(max_length=100)
    message = models.TextField()
    notification_type_choice = (
        ("user_notification", "User Notification"),
        ("news_notification", "News Notification"),
        ("system_notification", "System Notification"),
    )
    notification_type = models.CharField(
        max_length=50, choices=notification_type_choice, default="system_notification"
    )
    object_id = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    users_read = models.ManyToManyField(
        User, related_name="read_notifications", blank=True
    )

    def __str__(self):
        return self.title


class ContentReport(models.Model):
    TARGET_CHOICES = (
        ("job_offer", "Offre d'emploi"),
        ("user", "Profil utilisateur"),
    )
    REASON_CHOICES = (
        ("spam", "Spam / publicité"),
        ("scam", "Arnaque / fraude"),
        ("inappropriate", "Contenu inapproprié"),
        ("fake", "Fausse information"),
        ("harassment", "Harcèlement"),
        ("other", "Autre"),
    )
    STATUS_CHOICES = (
        ("pending", "En attente"),
        ("reviewed", "Examiné"),
        ("dismissed", "Rejeté"),
    )

    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="content_reports"
    )
    target_type = models.CharField(max_length=20, choices=TARGET_CHOICES)
    target_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    details = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Signalement"
        verbose_name_plural = "Signalements"

    def __str__(self):
        return f"{self.target_type}:{self.target_id} by {self.reporter_id}"
