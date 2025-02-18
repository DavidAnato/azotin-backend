from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app_job.models import Job, JobApplication, JobOffer
from app_notification.utils import create_user_notification
from app_profile.models import WorkerProfile

from .models import UserNotification

User = get_user_model()


# Signal pour nouveau utilisateur
@receiver(post_save, sender=User)
def notify_new_user(sender, instance, created, **kwargs):
    if created:
        create_user_notification(
            recipient=instance,
            message="Bienvenue sur notre plateforme ! 🎉",
            object={
                "type": "new_user",
                "user_id": instance.id,
                "email": instance.email,
            },
        )


# Signal pour nouvelle offre d'emploi
@receiver(post_save, sender=JobOffer)
def notify_job_offer(sender, instance, created, **kwargs):
    if created:
        # Notifier les travailleurs de la même catégorie
        workers = WorkerProfile.objects.filter(category=instance.category)
        for worker in workers:
            if worker.new_job_notification:  # Vérifie la préférence de notification
                create_user_notification(
                    recipient=worker.user,
                    message=f"Nouvelle offre d'emploi dans votre domaine : {instance.title}",
                    object={
                        "type": "new_job_offer",
                        "job_offer_id": instance.id,
                        "title": instance.title,
                        "category": instance.category.name,
                    },
                )


# Signal pour nouvelle candidature
@receiver(post_save, sender=JobApplication)
def notify_job_application(sender, instance, created, **kwargs):
    if created:
        create_user_notification(
            recipient=instance.job_offer.client.user,
            message=f"Nouvelle candidature pour votre offre : {instance.job_offer.title}",
            object={
                "type": "new_application",
                "job_offer_id": instance.job_offer.id,
                "applicant_id": instance.worker.user.id,
                "applicant_name": f"{instance.worker.user.first_name} {instance.worker.user.last_name}",
            },
        )


# Signal pour attribution d'un travail
@receiver(post_save, sender=Job)
def notify_job_assignment(sender, instance, created, **kwargs):
    if created:
        # Notifier le travailleur
        create_user_notification(
            recipient=instance.worker.user,
            message=f"Vous avez été sélectionné pour : {instance.job_offer.title}",
            object={
                "type": "job_assigned",
                "job_id": instance.id,
                "job_offer_id": instance.job_offer.id,
            },
        )

        # Notifier les autres candidats
        other_applicants = JobApplication.objects.filter(
            job_offer=instance.job_offer
        ).exclude(worker=instance.worker)

        for application in other_applicants:
            create_user_notification(
                recipient=application.worker.user,
                message=f"Le poste '{instance.job_offer.title}' a été attribué à un autre candidat",
                object={
                    "type": "job_assigned_others",
                    "job_offer_id": instance.job_offer.id,
                },
            )


@receiver([post_save, post_delete], sender=UserNotification)
def notification_status_update(sender, instance, **kwargs):
    channel_layer = get_channel_layer()

    # Vérifier s'il reste des notifications non lues
    has_unread = UserNotification.objects.filter(
        recipient=instance.recipient, is_read=False
    ).exists()

    # Envoyer la mise à jour au websocket
    async_to_sync(channel_layer.group_send)(
        f"notification_status_{instance.recipient.id}",
        {"type": "notification_status_update", "has_unread": has_unread},
    )
