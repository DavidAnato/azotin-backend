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
    )  # Added ManyToMany field

    def __str__(self):
        return self.title
