import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import Conversation, Message, MessageMedia


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        if self.scope["user"].is_anonymous:
            print("\033[91mConnection refusée: Utilisateur anonyme\033[0m")
            await self.close(code=403)
            return

        is_participant = await self.is_conversation_participant()
        if not is_participant:
            print(
                "\033[91mConnection refusée: L'utilisateur n'est pas participant\033[0m"
            )
            await self.close(code=403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(f"\033[92mNouvelle connexion au chat {self.conversation_id}\033[0m")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"\033[93mDéconnexion du chat {self.conversation_id}\033[0m")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action_type = data.get("type", "message")
            print(f"\033[94mMessage reçu - Type: {action_type}\033[0m")

            if action_type == "message":
                await self.handle_new_message(data)
            elif action_type == "mark_read":
                await self.handle_mark_read(data)
            elif action_type == "edit":
                await self.handle_edit_message(data)
            elif action_type == "delete":
                await self.handle_delete_message(data)

        except (KeyError, json.JSONDecodeError):
            print("\033[91mErreur de format JSON\033[0m")
            pass
        except Exception as e:
            print(f"\033[91mErreur inattendue: {str(e)}\033[0m")
            await self.close()

    async def handle_new_message(self, data):
        sender_id = self.scope["user"].id
        message_content = data.get("message")
        file = data.get("file")
        job_offer_id = data.get("job_offer_id")

        print(
            f"\033[96mNouveau message de {sender_id}:\n"
            f"Contenu: {message_content}\n"
            f"Fichier: {file}\n"
            f"Offre: {job_offer_id}\033[0m"
        )

        # Vérifier qu'au moins un type de contenu est présent
        if not any([message_content, file, job_offer_id]):
            print("\033[93mMessage vide ignoré\033[0m")
            return

        # Sauvegarder le message avec ses contenus
        saved_message = await self.save_message(
            content=message_content,
            sender_id=sender_id,
            file=file,
            job_offer_id=job_offer_id,
        )

        print(f"\033[92mMessage sauvegardé avec l'ID: {saved_message.id}\033[0m")

        # Préparer les données de base du message
        message_data = {
            "type": "chat_message",
            "message_id": saved_message.id,
            "sender_id": sender_id,
            "timestamp": saved_message.timestamp.isoformat(),
        }

        # Ajouter les données spécifiques selon le type de contenu
        if message_content:
            message_data["content"] = message_content

        if file and saved_message.medias.exists():
            message_data["media_url"] = saved_message.medias.first().file.url

        if job_offer_id:
            job_offer_data = await self.get_job_offer_data(job_offer_id)
            message_data["job_offer"] = job_offer_data

        # Envoyer au groupe de conversation
        print(f"\033[94mEnvoi au groupe {self.room_group_name}\033[0m")
        await self.channel_layer.group_send(self.room_group_name, message_data)

        # Préparer les données pour la mise à jour des participants
        update_data = {
            "type": "message_update",
            "update_type": "new_message",
            "conversation_id": self.conversation_id,
            "message_id": saved_message.id,
            "sender_id": sender_id,
            "timestamp": saved_message.timestamp.isoformat(),
            "status": "sent",
        }

        # Ajouter les mêmes données spécifiques
        if message_content:
            update_data["content"] = message_content
        if file and saved_message.medias.exists():
            update_data["media_url"] = saved_message.medias.first().file.url
        if job_offer_id:
            update_data["job_offer"] = job_offer_data

        # Envoyer aux participants individuels
        conversation_participants = await self.get_conversation_participants()
        print(f"\033[94mEnvoi aux participants: {conversation_participants}\033[0m")
        for participant_id in conversation_participants:
            unread_count = await self.get_unread_count(
                participant_id, self.conversation_id
            )
            participant_data = {**update_data, "unread_count": unread_count}
            await self.channel_layer.group_send(
                f"user_messages_{participant_id}", participant_data
            )

    async def handle_mark_read(self, data):
        conversation_id = self.conversation_id
        user_id = self.scope["user"].id

        print(
            f"\033[96mMarquage comme lu - Conversation: {conversation_id}, Utilisateur: {user_id}\033[0m"
        )

        await self.mark_messages_as_read(conversation_id, user_id)

        conversation_participants = await self.get_conversation_participants()
        for participant_id in conversation_participants:
            await self.channel_layer.group_send(
                f"user_messages_{participant_id}",
                {
                    "type": "message_update",
                    "update_type": "messages_read",
                    "conversation_id": conversation_id,
                    "reader_id": user_id,
                    "timestamp": timezone.now().isoformat(),
                },
            )

    async def handle_edit_message(self, data):
        message_id = data["message_id"]
        new_content = data["content"]
        user_id = self.scope["user"].id

        print(f"\033[96mÉdition du message {message_id} par {user_id}\033[0m")

        # Get the old content before updating
        old_content = await self.get_message_content(message_id)
        updated_message = await self.update_message(message_id, new_content, user_id)

        if updated_message:
            print("\033[92mMessage mis à jour avec succès\033[0m")
            # Notify chat room participants about the edit
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited_update",
                    "message_id": message_id,
                    "content": new_content,
                    "edited_at": updated_message.edited_at.isoformat(),
                },
            )

            # Check if this is the last message in the conversation
            is_last = await self.is_last_message(message_id)
            if is_last:
                conversation_participants = await self.get_conversation_participants()
                for participant_id in conversation_participants:
                    unread_count = await self.get_unread_count(
                        participant_id, self.conversation_id
                    )
                    await self.channel_layer.group_send(
                        f"user_messages_{participant_id}",
                        {
                            "type": "message_update",
                            "update_type": "message_edited",
                            "conversation_id": self.conversation_id,
                            "old_content": old_content,
                            "content": new_content,
                            "edited_at": updated_message.edited_at.isoformat(),
                            "unread_count": unread_count,
                        },
                    )

    async def handle_delete_message(self, data):
        message_id = data["message_id"]
        user_id = self.scope["user"].id

        print(f"\033[96mSuppression du message {message_id} par {user_id}\033[0m")

        # Check if it's the last message before deleting
        is_last = await self.is_last_message(message_id)
        new_last_message = None

        if is_last:
            # Get the previous message before deletion
            new_last_message = await self.get_previous_message(message_id)

        if await self.delete_message(message_id, user_id):
            print("\033[92mMessage supprimé avec succès\033[0m")
            # Notify chat room participants about the deletion
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "message_deleted_update", "message_id": message_id},
            )

            if is_last:
                conversation_participants = await self.get_conversation_participants()
                for participant_id in conversation_participants:
                    unread_count = await self.get_unread_count(
                        participant_id, self.conversation_id
                    )
                    message_data = {
                        "type": "message_update",
                        "update_type": "message_deleted",
                        "conversation_id": self.conversation_id,
                        "message_id": message_id,
                        "unread_count": unread_count,
                    }

                    if new_last_message:
                        message_data["new_last_message"] = {
                            "content": new_last_message.content,
                            "timestamp": new_last_message.timestamp.isoformat(),
                        }

                    await self.channel_layer.group_send(
                        f"user_messages_{participant_id}", message_data
                    )

    async def chat_message(self, event):
        # Supprimer le type du message avant l'envoi
        message_data = event.copy()
        message_type = message_data.pop("type")

        print(f"\033[94mEnvoi du message au client - Type: {message_type}\033[0m")
        await self.send(text_data=json.dumps({"type": message_type, **message_data}))

    async def messages_read_update(self, event):
        print("\033[94mEnvoi de la mise à jour de lecture\033[0m")
        await self.send(
            text_data=json.dumps(
                {
                    "type": "messages_read",
                    "reader_id": event["reader_id"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def message_edited_update(self, event):
        print("\033[94mEnvoi de la mise à jour d'édition\033[0m")
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_edited",
                    "message_id": event["message_id"],
                    "content": event["content"],
                    "edited_at": event["edited_at"],
                }
            )
        )

    async def message_deleted_update(self, event):
        print("\033[94mEnvoi de la mise à jour de suppression\033[0m")
        await self.send(
            text_data=json.dumps(
                {"type": "message_deleted", "message_id": event["message_id"]}
            )
        )

    @database_sync_to_async
    def save_message(self, content=None, sender_id=None, file=None, job_offer_id=None):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            message = Message.objects.create(
                conversation=conversation,
                sender_id=sender_id,
                content=content,
                job_offer_id=job_offer_id,
                status="sent",
            )

            if file:
                MessageMedia.objects.create(message=message, file=file)

            return message
        except Conversation.DoesNotExist:
            print("\033[91mErreur: Conversation non trouvée\033[0m")
            raise PermissionDenied("Conversation non trouvée")

    @database_sync_to_async
    def get_job_offer_data(self, job_offer_id):
        from app_job.models import JobOffer
        from app_job.serializers import JobOfferSerializer

        try:
            print(f"\033[94mRécupération des données de l'offre {job_offer_id}\033[0m")
            job_offer = JobOffer.objects.get(id=job_offer_id)
            serialized_data = JobOfferSerializer(job_offer).data
            print(f"\033[92mDonnées de l'offre récupérées avec succès\033[0m")
            return serialized_data
        except JobOffer.DoesNotExist:
            print(f"\033[91mErreur: Offre {job_offer_id} non trouvée\033[0m")
            return None
        except Exception as e:
            print(f"\033[91mErreur lors de la récupération de l'offre: {str(e)}\033[0m")
            return None

    @database_sync_to_async
    def mark_messages_as_read(self, conversation_id, user_id):
        Message.objects.filter(
            conversation_id=conversation_id, status__in=["sent", "received"]
        ).exclude(sender_id=user_id).update(status="read", read_at=timezone.now())

    @database_sync_to_async
    def update_message(self, message_id, new_content, user_id):
        try:
            message = Message.objects.get(
                id=message_id, sender_id=user_id, conversation_id=self.conversation_id
            )
            message.content = new_content
            message.edited_at = timezone.now()
            message.save()
            return message
        except Message.DoesNotExist:
            print(f"\033[91mErreur: Message {message_id} non trouvé\033[0m")
            return None

    @database_sync_to_async
    def delete_message(self, message_id, user_id):
        try:
            message = Message.objects.get(
                id=message_id, sender_id=user_id, conversation_id=self.conversation_id
            )
            message.delete()
            return True
        except Message.DoesNotExist:
            print(f"\033[91mErreur: Message {message_id} non trouvé\033[0m")
            return False

    @database_sync_to_async
    def is_conversation_participant(self):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.participants.filter(id=self.scope["user"].id).exists()
        except Conversation.DoesNotExist:
            print(
                f"\033[91mErreur: Conversation {self.conversation_id} non trouvée\033[0m"
            )
            return False

    @database_sync_to_async
    def get_conversation_participants(self):
        conversation = Conversation.objects.get(id=self.conversation_id)
        return list(conversation.participants.values_list("id", flat=True))

    @database_sync_to_async
    def is_last_message(self, message_id):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            last_message = conversation.messages.order_by("-timestamp").first()

            message_id_str = str(message_id)
            last_message_id_str = str(last_message.id) if last_message else None

            is_last = last_message and message_id_str == last_message_id_str

            return is_last
        except Conversation.DoesNotExist:
            print(
                f"\033[91mErreur: Conversation {self.conversation_id} non trouvée\033[0m"
            )
            return False

    @database_sync_to_async
    def get_message_content(self, message_id):
        try:
            message = Message.objects.get(id=message_id)
            return message.content
        except Message.DoesNotExist:
            print(f"\033[91mErreur: Message {message_id} non trouvé\033[0m")
            return None

    @database_sync_to_async
    def get_previous_message(self, message_id):
        try:
            current_message = Message.objects.get(id=message_id)
            return (
                Message.objects.filter(
                    conversation_id=self.conversation_id,
                    timestamp__lt=current_message.timestamp,
                )
                .order_by("-timestamp")
                .first()
            )
        except Message.DoesNotExist:
            print(f"\033[91mErreur: Message {message_id} non trouvé\033[0m")
            return None

    @database_sync_to_async
    def get_unread_count(self, user_id, conversation_id):
        return (
            Message.objects.filter(
                conversation_id=conversation_id,
                status__in=["sent", "received"],
                conversation__participants=user_id,
            )
            .exclude(sender_id=user_id)
            .count()
        )


class MessageListConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close(code=403)
            return

        self.user_group_name = f"user_messages_{self.user.id}"

        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def message_update(self, event):
        """
        Cette méthode doit correspondre exactement au "type" envoyé dans group_send
        """
        update_type = event["update_type"]

        if update_type == "new_message":
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "new_message",
                        "conversation_id": event["conversation_id"],
                        "unread_count": event.get("unread_count", 0),
                        "message": {
                            "id": event["message_id"],
                            "sender": event["sender_id"],
                            "content": event.get("content"),
                            "media_url": event.get("media_url"),
                            "job_offer": event.get("job_offer"),
                            "timestamp": event["timestamp"],
                            "status": event["status"],
                        },
                    }
                )
            )

        elif update_type == "messages_read":
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "messages_read",
                        "conversation_id": event["conversation_id"],
                        "reader_id": event["reader_id"],
                        "timestamp": event["timestamp"],
                        "unread_count": 0,
                    }
                )
            )

        elif update_type == "message_edited":
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "message_edited",
                        "conversation_id": event["conversation_id"],
                        "unread_count": event.get("unread_count", 0),
                        "message_id": event["message_id"],
                        "content": event["content"],
                        "edited_at": event["edited_at"],
                    }
                )
            )

        elif update_type == "message_deleted":
            response_data = {
                "type": "message_deleted",
                "conversation_id": event["conversation_id"],
                "unread_count": event.get("unread_count", 0),
                "message_id": event["message_id"],
            }

            if "new_last_message" in event:
                response_data["new_last_message"] = event["new_last_message"]

            await self.send(text_data=json.dumps(response_data))
