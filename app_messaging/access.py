"""Règles d'accès messagerie : seul le client initie une conversation."""

from app_profile.models import ClientProfile, WorkerProfile

WORKER_CANNOT_INITIATE = (
    "Seul le client peut démarrer une conversation. "
    "Vous pourrez répondre une fois que le client vous aura contacté."
)


def user_is_worker(user) -> bool:
    profile_type = getattr(user, "profile_type", "") or ""
    if profile_type == "worker":
        return True
    if profile_type == "employer":
        return False
    return WorkerProfile.objects.filter(user=user).exists()


def user_is_client(user) -> bool:
    profile_type = getattr(user, "profile_type", "") or ""
    if profile_type == "employer":
        return True
    if profile_type == "worker":
        return False
    return ClientProfile.objects.filter(user=user).exists()


def worker_blocked_from_new_conversation(user, existing_conversation) -> bool:
    return user_is_worker(user) and existing_conversation is None


def worker_blocked_from_first_message(user, conversation) -> bool:
    if not user_is_worker(user):
        return False
    return not conversation.messages.exists()
