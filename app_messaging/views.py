from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .broadcast import broadcast_new_message
from .member_utils import clear_inbox_flags, get_or_create_member_state
from .access import (
    WORKER_CANNOT_INITIATE,
    worker_blocked_from_first_message,
    worker_blocked_from_new_conversation,
)
from .message_visibility import (
    broadcast_message_event,
    can_delete_for_everyone,
    hide_message_for_user,
    hide_messages_for_user,
    mark_deleted_for_everyone,
    undo_deleted_for_everyone,
    unhide_message_for_user,
    unhide_messages_for_user,
    visible_messages_qs,
)
from .models import Conversation, ConversationMemberState, Message, MessageMedia
from .serializers import ConversationSerializer, MessageSerializer


def _user_conversations_qs(user, *, archived: bool = False, include_hidden: bool = False):
    qs = Conversation.objects.filter(participants=user)

    if not include_hidden:
        hidden_ids = ConversationMemberState.objects.filter(
            user=user, hidden_at__isnull=False
        ).values_list("conversation_id", flat=True)
        qs = qs.exclude(id__in=hidden_ids)

    archived_ids = ConversationMemberState.objects.filter(
        user=user, archived_at__isnull=False
    ).values_list("conversation_id", flat=True)

    if archived:
        qs = qs.filter(id__in=archived_ids)
    else:
        qs = qs.exclude(id__in=archived_ids)

    return qs.distinct().order_by("-updated_at")


class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        archived = self.request.query_params.get("archived") in ("1", "true", "True")
        return _user_conversations_qs(self.request.user, archived=archived)


class ConversationDetailView(generics.RetrieveAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Détail accessible même si archivé/masqué (pour restore)
        return Conversation.objects.filter(participants=self.request.user)

    def delete(self, request, *args, **kwargs):
        """Supprime la conversation pour soi : messages actuels retirés via hidden_for."""
        conversation = self.get_object()
        hidden_ids = hide_messages_for_user(conversation, request.user)
        state = get_or_create_member_state(conversation, request.user)
        state.hidden_at = timezone.now()
        state.archived_at = None
        state.save(update_fields=["hidden_at", "archived_at", "updated_at"])
        return Response(
            {"hidden_message_ids": hidden_ids},
            status=status.HTTP_200_OK,
        )


class ConversationRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        conversation = Conversation.objects.filter(
            pk=pk, participants=request.user
        ).first()
        if not conversation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        state = get_or_create_member_state(conversation, request.user)
        state.hidden_at = None
        state.save(update_fields=["hidden_at", "updated_at"])

        # Annulation : réaffiche les messages retirés lors de la suppression conversation
        message_ids = request.data.get("hidden_message_ids") or []
        if message_ids:
            unhide_messages_for_user(message_ids, request.user)

        return Response(
            ConversationSerializer(conversation, context={"request": request}).data
        )


class ConversationArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        conversation = Conversation.objects.filter(
            pk=pk, participants=request.user
        ).first()
        if not conversation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        unarchive = request.data.get("unarchive") in (True, "true", "1", 1)
        state = get_or_create_member_state(conversation, request.user)
        state.archived_at = None if unarchive else timezone.now()
        state.hidden_at = None
        state.save(update_fields=["archived_at", "hidden_at", "updated_at"])
        return Response(
            {
                "archived": state.archived_at is not None,
                "conversation": ConversationSerializer(
                    conversation, context={"request": request}
                ).data,
            }
        )


class ConversationMuteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        conversation = Conversation.objects.filter(
            pk=pk, participants=request.user
        ).first()
        if not conversation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        muted = request.data.get("muted")
        if muted is None:
            return Response(
                {"error": "muted (bool) requis"}, status=status.HTTP_400_BAD_REQUEST
            )
        state = get_or_create_member_state(conversation, request.user)
        state.muted = bool(muted) if not isinstance(muted, str) else muted.lower() in (
            "1",
            "true",
            "yes",
        )
        state.save(update_fields=["muted", "updated_at"])
        return Response({"muted": state.muted})


class ConversationMarkUnreadView(APIView):
    """Marquer / démarquer une conversation comme non lue (manuel)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        conversation = Conversation.objects.filter(
            pk=pk, participants=request.user
        ).first()
        if not conversation:
            return Response(status=status.HTTP_404_NOT_FOUND)
        unread = request.data.get("unread", True)
        if isinstance(unread, str):
            unread = unread.lower() in ("1", "true", "yes")
        state = get_or_create_member_state(conversation, request.user)
        state.marked_unread = bool(unread)
        state.save(update_fields=["marked_unread", "updated_at"])
        return Response(
            {
                "marked_unread": state.marked_unread,
                "unread_count": ConversationSerializer(
                    conversation, context={"request": request}
                ).data.get("unread_count", 0),
            }
        )


class ConversationCreateView(generics.CreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        other_participant_id = request.query_params.get("participant_id")

        if not other_participant_id:
            return Response(
                {"error": "L'ID du participant est requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_conversation = (
            Conversation.objects.filter(participants=self.request.user)
            .filter(participants=other_participant_id)
            .first()
        )

        if existing_conversation:
            clear_inbox_flags(existing_conversation, request.user)
            serializer = self.get_serializer(existing_conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        if worker_blocked_from_new_conversation(self.request.user, None):
            return Response(
                {
                    "detail": WORKER_CANNOT_INITIATE,
                    "code": "client_must_initiate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        conversation = Conversation.objects.create()
        conversation.participants.add(self.request.user, other_participant_id)

        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.request.query_params.get("conversation_id")
        if conversation_id:
            unread_messages = (
                Message.objects.filter(
                    conversation_id=conversation_id,
                    status__in=["sent", "received"],
                    conversation__participants=self.request.user,
                )
                .exclude(sender=self.request.user)
                .exclude(hidden_for=self.request.user)
                .exclude(deleted_for_everyone=True)
            )

            ids = list(unread_messages.values_list("id", flat=True))
            now = timezone.now()
            if ids:
                unread_messages.update(status="read", read_at=now)
                from .broadcast import broadcast_message_status

                broadcast_message_status(
                    conversation_id, ids, "read", reader_id=self.request.user.id
                )

            # Ouvrir le fil = plus de marquage manuel non lu
            from .models import ConversationMemberState

            ConversationMemberState.objects.filter(
                conversation_id=conversation_id, user=self.request.user
            ).update(marked_unread=False)

            return visible_messages_qs(conversation_id, self.request.user)
        return Message.objects.none()


class MessageCreateView(APIView):
    """Création REST multipart — idéal pour médias lourds (hors WebSocket)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        content = request.data.get("content") or request.data.get("message") or ""
        job_offer_id = request.data.get("job_offer_id") or None
        local_id = request.data.get("local_id") or None

        if not conversation_id:
            return Response(
                {"error": "conversation_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation = Conversation.objects.filter(
            id=conversation_id, participants=request.user
        ).first()
        if not conversation:
            return Response(
                {"error": "Conversation introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if worker_blocked_from_first_message(request.user, conversation):
            return Response(
                {
                    "detail": WORKER_CANNOT_INITIATE,
                    "code": "client_must_initiate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if job_offer_id in ("", "null", "undefined", 0, "0"):
            job_offer_id = None

        files = request.FILES.getlist("files") or request.FILES.getlist("file")
        if not content and not files and not job_offer_id:
            return Response(
                {"error": "Message vide"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reply_to = None
        reply_to_id = request.data.get("reply_to_id")
        if reply_to_id not in (None, "", "null", "undefined"):
            try:
                reply_to = Message.objects.filter(
                    id=int(reply_to_id), conversation=conversation
                ).first()
            except (TypeError, ValueError):
                reply_to = None

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content or None,
            job_offer_id=job_offer_id,
            status="sent",
            reply_to=reply_to,
        )

        for f in files:
            MessageMedia.objects.create(message=message, file=f)

        broadcast_new_message(message, local_id=local_id)
        return Response(
            MessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MessageDeleteView(APIView):
    """Supprimer pour moi ou pour tous."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        message = (
            Message.objects.filter(pk=pk, conversation__participants=request.user)
            .select_related("conversation")
            .first()
        )
        if not message:
            return Response(status=status.HTTP_404_NOT_FOUND)

        scope = (request.data.get("scope") or "me").lower()
        if scope not in ("me", "everyone"):
            return Response(
                {"error": "scope doit être me ou everyone"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if scope == "me":
            hide_message_for_user(message, request.user)
            return Response(
                {
                    "scope": "me",
                    "message_id": message.id,
                    "conversation_id": message.conversation_id,
                }
            )

        if not can_delete_for_everyone(message, request.user):
            return Response(
                {
                    "error": "Suppression pour tous indisponible (délai dépassé ou non auteur)"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mark_deleted_for_everyone(message)
        broadcast_message_event(
            message.conversation_id,
            {
                "type": "message_deleted_for_everyone_event",
                "message_id": message.id,
                "conversation_id": message.conversation_id,
                "deleted_by": request.user.id,
            },
        )
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
            for participant_id in message.conversation.participants.values_list(
                "id", flat=True
            ):
                async_to_sync(channel_layer.group_send)(
                    f"user_messages_{participant_id}",
                    {
                        "type": "message_update",
                        "update_type": "message_deleted_for_everyone",
                        "conversation_id": message.conversation_id,
                        "message_id": message.id,
                    },
                )

        return Response(
            {
                "scope": "everyone",
                "message_id": message.id,
                "conversation_id": message.conversation_id,
                "message": MessageSerializer(
                    message, context={"request": request}
                ).data,
            }
        )


class MessageRestoreView(APIView):
    """Annuler une suppression (pour moi ou pour tous)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        message = (
            Message.objects.filter(pk=pk, conversation__participants=request.user)
            .select_related("conversation")
            .first()
        )
        if not message:
            return Response(status=status.HTTP_404_NOT_FOUND)

        scope = (request.data.get("scope") or "me").lower()

        if scope == "me":
            unhide_message_for_user(message, request.user)
            return Response(
                {
                    "scope": "me",
                    "message_id": message.id,
                    "message": MessageSerializer(
                        message, context={"request": request}
                    ).data,
                }
            )

        if scope == "everyone":
            if message.sender_id != request.user.id:
                return Response(status=status.HTTP_403_FORBIDDEN)
            if not message.deleted_for_everyone:
                return Response(
                    MessageSerializer(message, context={"request": request}).data
                )
            undo_deleted_for_everyone(message)
            broadcast_message_event(
                message.conversation_id,
                {
                    "type": "message_restored_event",
                    "message_id": message.id,
                    "conversation_id": message.conversation_id,
                    "message": MessageSerializer(
                        message, context={"request": request}
                    ).data,
                },
            )
            return Response(
                {
                    "scope": "everyone",
                    "message_id": message.id,
                    "message": MessageSerializer(
                        message, context={"request": request}
                    ).data,
                }
            )

        return Response(
            {"error": "scope invalide"}, status=status.HTTP_400_BAD_REQUEST
        )


class MarkMessagesAsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        if not conversation_id:
            return Response(
                {"error": "conversation_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not Conversation.objects.filter(
            id=conversation_id, participants=request.user
        ).exists():
            return Response(
                {"error": "Vous n'êtes pas autorisé à accéder à cette conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        unread_messages = (
            Message.objects.filter(
                conversation_id=conversation_id,
                status__in=["sent", "received"],
                conversation__participants=request.user,
            )
            .exclude(sender=request.user)
            .exclude(hidden_for=request.user)
            .exclude(deleted_for_everyone=True)
        )

        ids = list(unread_messages.values_list("id", flat=True))
        now = timezone.now()
        for message in unread_messages:
            message.status = "read"
            message.read_at = now
            message.save()

        if ids:
            from .broadcast import broadcast_message_status

            broadcast_message_status(
                conversation_id, ids, "read", reader_id=request.user.id
            )

        from .models import ConversationMemberState

        ConversationMemberState.objects.filter(
            conversation_id=conversation_id, user=request.user
        ).update(marked_unread=False)

        return Response({"status": "success", "updated": len(ids)})
