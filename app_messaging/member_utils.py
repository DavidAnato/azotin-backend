from django.utils import timezone

from .models import Conversation, ConversationMemberState


def get_or_create_member_state(conversation: Conversation, user) -> ConversationMemberState:
    state, _ = ConversationMemberState.objects.get_or_create(
        conversation=conversation, user=user
    )
    return state


def clear_inbox_flags(conversation: Conversation, user=None) -> None:
    """
    Réaffiche la conversation dans l'inbox (ex. nouveau message).
    Si user est None, pour tous les participants.
    """
    qs = ConversationMemberState.objects.filter(conversation=conversation)
    if user is not None:
        qs = qs.filter(user=user)
    qs.update(hidden_at=None, archived_at=None, updated_at=timezone.now())
