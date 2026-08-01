"""Helpers de visibilité / suppression des messages."""

from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from .models import Message

DELETE_FOR_EVERYONE_WINDOW = timedelta(minutes=10)
EDIT_WINDOW = timedelta(minutes=10)


def visible_messages_qs(conversation_id, user):
    """Messages visibles pour un utilisateur (hors « supprimer pour moi »)."""
    return (
        Message.objects.filter(conversation_id=conversation_id)
        .exclude(hidden_for=user)
        .order_by("-timestamp")
    )


def can_delete_for_everyone(message: Message, user) -> bool:
    if message.sender_id != user.id:
        return False
    if message.deleted_for_everyone:
        return False
    return timezone.now() - message.timestamp <= DELETE_FOR_EVERYONE_WINDOW


def can_edit(message: Message, user) -> bool:
    if message.sender_id != user.id:
        return False
    if message.deleted_for_everyone:
        return False
    return timezone.now() - message.timestamp <= EDIT_WINDOW


def hide_messages_for_user(conversation, user):
    """Retire tous les messages actuels pour cet utilisateur. Retourne les IDs touchés."""
    qs = Message.objects.filter(conversation=conversation).exclude(hidden_for=user)
    ids = list(qs.values_list("id", flat=True))
    Through = Message.hidden_for.through
    Through.objects.bulk_create(
        [Through(message_id=mid, user_id=user.id) for mid in ids],
        ignore_conflicts=True,
    )
    return ids


def unhide_messages_for_user(message_ids, user):
    if not message_ids:
        return
    Message.hidden_for.through.objects.filter(
        message_id__in=message_ids, user_id=user.id
    ).delete()


def hide_message_for_user(message: Message, user):
    message.hidden_for.add(user)


def unhide_message_for_user(message: Message, user):
    message.hidden_for.remove(user)


def mark_deleted_for_everyone(message: Message):
    message.deleted_for_everyone = True
    message.deleted_for_everyone_at = timezone.now()
    message.save(update_fields=["deleted_for_everyone", "deleted_for_everyone_at"])


def undo_deleted_for_everyone(message: Message):
    message.deleted_for_everyone = False
    message.deleted_for_everyone_at = None
    message.save(update_fields=["deleted_for_everyone", "deleted_for_everyone_at"])


def broadcast_message_event(conversation_id, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"chat_{conversation_id}", payload
    )


def last_visible_message(conversation, user):
    return (
        Message.objects.filter(conversation=conversation)
        .exclude(hidden_for=user)
        .order_by("-timestamp")
        .first()
    )


def unread_visible_count(conversation, user):
    count = (
        Message.objects.filter(
            conversation=conversation,
            status__in=["sent", "received"],
        )
        .exclude(sender=user)
        .exclude(hidden_for=user)
        .exclude(deleted_for_everyone=True)
        .count()
    )
    state = conversation.member_states.filter(user=user).only("marked_unread").first()
    if state and state.marked_unread:
        return max(count, 1)
    return count
