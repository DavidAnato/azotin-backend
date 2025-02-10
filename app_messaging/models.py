from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Conversation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    participants = models.ManyToManyField(User, related_name="conversations")


class Message(models.Model):
    MESSAGE_STATUS = (("sent", "Envoyé"), ("received", "Reçu"), ("read", "Lu"))

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField(null=True, blank=True)
    job_offer = models.ForeignKey(
        "app_job.JobOffer",
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=MESSAGE_STATUS, default="sent")
    edited_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)


class MessageMedia(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="medias"
    )
    file = models.FileField(upload_to="media/")
    created_at = models.DateTimeField(auto_now_add=True)
