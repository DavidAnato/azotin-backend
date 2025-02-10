from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserNotification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.TextField()
    object = models.JSONField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification pour {self.recipient.first_name}: {self.message}"

    class Meta:
        ordering = ["-created_at"]
