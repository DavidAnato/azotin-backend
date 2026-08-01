from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Conversation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    participants = models.ManyToManyField(User, related_name="conversations")


class ConversationMemberState(models.Model):
    """Préférences / masquage par utilisateur — les messages restent en base."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="member_states"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversation_states"
    )
    # Soft-hide inbox (suppression côté user uniquement)
    hidden_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    muted = models.BooleanField(default=False)
    # Marquage manuel non lu (style WhatsApp)
    marked_unread = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("conversation", "user")
        verbose_name = "État conversation (membre)"
        verbose_name_plural = "États conversation (membres)"

    def __str__(self):
        return f"conv={self.conversation_id} user={self.user_id}"


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
    edited_at = models.DateTimeField(null=True, blank=True, default=None)
    read_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    # Utilisateurs pour qui ce message est réellement retiré (suppr. pour moi / clear conversation)
    hidden_for = models.ManyToManyField(
        User, blank=True, related_name="hidden_messages"
    )
    # Suppression pour tous (placeholder type WhatsApp)
    deleted_for_everyone = models.BooleanField(default=False)
    deleted_for_everyone_at = models.DateTimeField(null=True, blank=True)


class MessageMedia(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="medias"
    )
    file = models.FileField(upload_to="media/")
    created_at = models.DateTimeField(auto_now_add=True)
