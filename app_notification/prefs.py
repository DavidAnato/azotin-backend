from authentication.models import UserSettings


def get_notification_settings(user):
    settings, _ = UserSettings.objects.get_or_create(user=user)
    return settings


def user_wants_message_notification(user) -> bool:
    """Préférences messages (worker_profile ou push global pour les clients)."""
    worker_profile = getattr(user, "worker_profile", None)
    if worker_profile is not None:
        return bool(worker_profile.new_message_notification)
    return bool(get_notification_settings(user).notification_push)
