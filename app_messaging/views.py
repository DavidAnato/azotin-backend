from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer


class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user).order_by(
            "-updated_at"
        )


class ConversationDetailView(generics.RetrieveAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)


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

        # Rechercher une conversation existante avec les deux participants
        existing_conversation = (
            Conversation.objects.filter(participants=self.request.user)
            .filter(participants=other_participant_id)
            .first()
        )

        if existing_conversation:
            serializer = self.get_serializer(existing_conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Créer une nouvelle conversation si elle n'existe pas
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
            # Récupérer les messages
            messages = Message.objects.filter(conversation_id=conversation_id).order_by(
                "-timestamp"
            )

            # Marquer comme lus les messages non envoyés par l'utilisateur courant
            unread_messages = Message.objects.filter(
                conversation_id=conversation_id,
                status__in=["sent", "received"],
                conversation__participants=self.request.user,
            ).exclude(sender=self.request.user)

            for message in unread_messages:
                message.status = "read"
                message.read_at = timezone.now()
                message.save()

            return messages
        return Message.objects.none()


class MarkMessagesAsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        if not conversation_id:
            return Response(
                {"error": "conversation_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vérifier si l'utilisateur est participant de la conversation
        if not Conversation.objects.filter(
            id=conversation_id, participants=request.user
        ).exists():
            return Response(
                {"error": "Vous n'êtes pas autorisé à accéder à cette conversation"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Marquer tous les messages non lus comme lus
        unread_messages = Message.objects.filter(
            conversation_id=conversation_id,
            status__in=["sent", "received"],
            conversation__participants=request.user,
        ).exclude(sender=request.user)

        for message in unread_messages:
            message.status = "read"
            message.read_at = timezone.now()
            message.save()

        return Response({"status": "success"})
