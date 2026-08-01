import asyncio

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from app_job.models import Job, JobApplication, JobOffer
from app_notification.prefs import get_notification_settings
from app_notification.utils import (
    create_user_notification,
    send_email_if_configured,
    send_push_notification,
    send_sms_if_configured,
)
from app_notification.sse import publish_notification_sse
from app_profile.models import WorkerProfile
from authentication.models import UserSettings

from .models import NotificationToken, UserNotification

User = get_user_model()


def run_async(coroutine):
    """Exécute une coroutine de manière synchrone"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)


# Signal pour nouveau utilisateur
@receiver(post_save, sender=User)
def notify_new_user(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.get_or_create(user=instance)
        create_user_notification(
            recipient=instance,
            message="Bienvenue sur notre plateforme ! 🎉",
            object={
                "type": "new_user",
                "user_id": instance.id,
                "email": instance.email,
            },
        )
        # Envoyer notification push
        tokens = NotificationToken.objects.filter(user=instance)
        for token in tokens:
            run_async(
                send_push_notification(
                    token=token.token,
                    title="Bienvenue sur JobHub !",
                    body="Bienvenue sur notre plateforme ! 🎉",
                    data={
                        "type": "new_user",
                        "user_id": instance.id,
                    },
                )
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
                # Envoyer notification push
                tokens = NotificationToken.objects.filter(user=worker.user)
                for token in tokens:
                    run_async(
                        send_push_notification(
                            token=token.token,
                            title="Nouvelle offre d'emploi",
                            body=f"Nouvelle offre dans votre domaine : {instance.title}",
                            data={
                                "type": "new_job_offer",
                                "job_offer_id": instance.id,
                            },
                        )
                    )
                settings = get_notification_settings(worker.user)
                if settings.notification_sms:
                    send_sms_if_configured(
                        worker.user.phone_number,
                        f"Nouvelle offre d'emploi dans votre domaine : {instance.title}",
                    )
                if settings.notification_email:
                    send_email_if_configured(
                        worker.user.email,
                        f"Nouvelle offre d'emploi dans votre domaine : {instance.title}",
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
        # Envoyer notification push
        tokens = NotificationToken.objects.filter(user=instance.job_offer.client.user)
        for token in tokens:
            run_async(
                send_push_notification(
                    token=token.token,
                    title="Nouvelle candidature",
                    body=f"Nouvelle candidature pour : {instance.job_offer.title}",
                    data={
                        "type": "new_application",
                        "job_offer_id": instance.job_offer.id,
                    },
                )
            )
        settings = get_notification_settings(instance.job_offer.client.user)
        if settings.notification_sms:
            send_sms_if_configured(
                instance.job_offer.client.user.phone_number,
                f"Nouvelle candidature pour : {instance.job_offer.title}",
            )
        if settings.notification_email:
            send_email_if_configured(
                instance.job_offer.client.user.email,
                f"Nouvelle candidature pour : {instance.job_offer.title}",
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
        # Envoyer notification push au travailleur sélectionné
        tokens = NotificationToken.objects.filter(user=instance.worker.user)
        for token in tokens:
            run_async(
                send_push_notification(
                    token=token.token,
                    title="Mission attribuée",
                    body=f"Vous avez été sélectionné pour : {instance.job_offer.title}",
                    data={
                        "type": "job_assigned",
                        "job_id": instance.id,
                    },
                )
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
            # Envoyer notification push aux autres candidats
            tokens = NotificationToken.objects.filter(user=application.worker.user)
            for token in tokens:
                run_async(
                    send_push_notification(
                        token=token.token,
                        title="Mission attribuée",
                        body=f"Le poste '{instance.job_offer.title}' a été attribué à un autre candidat",
                        data={
                            "type": "job_assigned_others",
                            "job_offer_id": instance.job_offer.id,
                        },
                    )
                )
            settings = get_notification_settings(application.worker.user)
            if settings.notification_sms:
                send_sms_if_configured(
                    application.worker.user.phone_number,
                    f"Le poste '{instance.job_offer.title}' a été attribué à un autre candidat",
                )
            if settings.notification_email:
                send_email_if_configured(
                    application.worker.user.email,
                    f"Le poste '{instance.job_offer.title}' a été attribué à un autre candidat",
                )


@receiver([post_save, post_delete], sender=UserNotification)
def notification_status_update(sender, instance, **kwargs):
    channel_layer = get_channel_layer()

    # Vérifier s'il reste des notifications non lues
    has_unread = UserNotification.objects.filter(
        recipient=instance.recipient, is_read=False
    ).exists()

    try:
        async_to_sync(channel_layer.group_send)(
            f"notification_status_{instance.recipient.id}",
            {"type": "notification_status_update", "has_unread": has_unread},
        )
    except Exception:
        pass

    publish_notification_sse(
        instance.recipient.id,
        {"type": "notification_status", "has_unread": has_unread},
    )
