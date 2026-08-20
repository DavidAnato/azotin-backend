import base64
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
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

        from .presence import presence_connect

        await database_sync_to_async(presence_connect)(self.scope["user"].id)

        # Messages de l'autre → "received" (livré) dès qu'on ouvre le chat
        updated_ids = await self.mark_messages_as_received(
            self.conversation_id, self.scope["user"].id
        )
        if updated_ids:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_status_update",
                    "message_ids": updated_ids,
                    "status": "received",
                    "reader_id": self.scope["user"].id,
                    "timestamp": timezone.now().isoformat(),
                },
            )

    async def disconnect(self, close_code):
        from .presence import presence_disconnect

        if not self.scope["user"].is_anonymous:
            await database_sync_to_async(presence_disconnect)(self.scope["user"].id)
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
            elif action_type in ("typing", "typing_start", "typing_stop"):
                await self.handle_typing(data)

        except json.JSONDecodeError as e:
            print(f"\033[91mErreur de format JSON: {str(e)}\033[0m")
            print(f"\033[91mDonnées reçues: {text_data}\033[0m")
            pass
        except Exception as e:
            print(f"\033[91mErreur inattendue: {str(e)}\033[0m")
            await self.close()

    async def handle_typing(self, data):
        is_typing = data.get("type") != "typing_stop" and data.get("typing", True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_update",
                "user_id": self.scope["user"].id,
                "typing": bool(is_typing),
            },
        )
    async def handle_new_message(self, data):
        print("\033[95m=== Nouveau message reçu ===\033[0m")
        print(f"\033[95mContenu du message: {data.get('message')}\033[0m")
        print(f"\033[95mID de l'offre d'emploi: {data.get('job_offer_id')}\033[0m")

        files_data = data.get("files", [])
        if files_data:
            print(f"\033[95mNombre de fichiers détectés: {len(files_data)}\033[0m")
            for file_data in files_data:
                print(f"\033[95mInfo fichier: {file_data}\033[0m")

        # Traitement des fichiers
        processed_files = []
        for file_data in files_data:
            try:
                print("\033[94m=== Traitement du fichier multimédia ===\033[0m")
                # Les données sont directement dans file_data
                file_name = file_data.get("name", "file")
                file_type = file_data.get("type", "")
                file_content = file_data.get("content", "")

                print(f"\033[94mNom du fichier: {file_name}\033[0m")
                print(f"\033[94mType du fichier: {file_type}\033[0m")
                print(
                    f"\033[94mTaille du contenu base64: {len(file_content)} caractères\033[0m"
                )

                # Décodage du contenu base64
                format, content = file_content.split(";base64,")
                print(f"\033[94mFormat du fichier: {format}\033[0m")

                binary_content = base64.b64decode(content)
                print(
                    f"\033[94mTaille du fichier décodé: {len(binary_content)} bytes\033[0m"
                )

                processed_file = ContentFile(binary_content, name=file_name)
                processed_files.append(processed_file)
                print(
                    f"\033[92mFichier traité avec succès: {processed_file.name}\033[0m"
                )

            except Exception as e:
                print(f"\033[91mErreur de traitement du fichier: {str(e)}\033[0m")
                print(f"\033[91mDétails de l'erreur: {type(e).__name__}\033[0m")
                continue

        # Sauvegarde du message avec les fichiers traités
        saved_message_data = await self.save_message(
            content=data.get("message"),
            sender_id=self.scope["user"].id,
            files=processed_files,
            job_offer_id=data.get("job_offer_id"),
            local_id=data.get("local_id"),
            reply_to_id=data.get("reply_to_id"),
        )

        if saved_message_data and saved_message_data.get("error"):
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "code": saved_message_data.get("code"),
                        "detail": saved_message_data.get("detail"),
                        "local_id": saved_message_data.get("local_id"),
                    }
                )
            )
            return

        print("\033[95m=== Données du message sauvegardé ===\033[0m")
        print(f"\033[95mID du message: {saved_message_data['id']}\033[0m")
        print(f"\033[95mContenu: {saved_message_data['content']}\033[0m")
        print(f"\033[95mDate: {saved_message_data['timestamp']}\033[0m")
        if saved_message_data["medias"]:
            for media in saved_message_data["medias"]:
                print(f"\033[95mMédia: {media['file']}\033[0m")
                print(f"\033[95mURL du média: {media['file']}\033[0m")
        if saved_message_data["job_offer"]:
            print(
                f"\033[95mOffre d'emploi associée: {saved_message_data['job_offer']}\033[0m"
            )

        # Préparer les données de base du message
        message_data = {"type": "chat_message", **saved_message_data}

        if data.get("job_offer_id"):
            job_offer_data = await self.get_job_offer_data(data.get("job_offer_id"))
            message_data["job_offer"] = job_offer_data

        # Avant l'envoi au groupe
        print("\033[95m=== Données envoyées au groupe ===\033[0m")
        print(f"\033[95mMessage data: {json.dumps(message_data, indent=2)}\033[0m")

        await self.channel_layer.group_send(self.room_group_name, message_data)

        # Préparer les données pour la mise à jour des participants
        update_data = {
            "type": "message_update",
            "update_type": "new_message",
            "conversation_id": self.conversation_id,
            "message_id": saved_message_data["id"],
            "sender_id": self.scope["user"].id,
            "timestamp": saved_message_data["timestamp"],
            "status": saved_message_data["status"],
        }

        # Ajouter les mêmes données spécifiques
        if saved_message_data["content"]:
            update_data["content"] = saved_message_data["content"]
        if saved_message_data["medias"]:
            update_data["media_urls"] = [
                media["file"] for media in saved_message_data["medias"]
            ]
        if data.get("job_offer_id"):
            update_data["job_offer"] = job_offer_data

        # Avant l'envoi aux participants
        print("\033[95m=== Données envoyées aux participants ===\033[0m")
        print(f"\033[95mUpdate data: {json.dumps(update_data, indent=2)}\033[0m")

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

        updated_ids = await self.mark_messages_as_read(conversation_id, user_id)

        if updated_ids:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_status_update",
                    "message_ids": updated_ids,
                    "status": "read",
                    "reader_id": user_id,
                    "timestamp": timezone.now().isoformat(),
                },
            )

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

        if not updated_message:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "error": "edit_unavailable",
                        "message_id": message_id,
                    }
                )
            )
            return

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
                        "message_id": message_id,
                        "old_content": old_content,
                        "content": new_content,
                        "edited_at": updated_message.edited_at.isoformat(),
                        "unread_count": unread_count,
                    },
                )

    async def handle_delete_message(self, data):
        message_id = data["message_id"]
        user_id = self.scope["user"].id
        scope = (data.get("scope") or "everyone").lower()

        print(
            f"\033[96mSuppression message {message_id} par {user_id} scope={scope}\033[0m"
        )

        if scope == "me":
            ok = await self.hide_message_for_me(message_id, user_id)
            if ok:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "message_hidden",
                            "message_id": message_id,
                            "scope": "me",
                        }
                    )
                )
            return

        result = await self.delete_message_for_everyone(message_id, user_id)
        if not result:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "error": "delete_for_everyone_unavailable",
                        "message_id": message_id,
                    }
                )
            )
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "message_deleted_for_everyone_event",
                "message_id": message_id,
                "conversation_id": int(self.conversation_id),
                "deleted_by": user_id,
            },
        )

        conversation_participants = await self.get_conversation_participants()
        for participant_id in conversation_participants:
            await self.channel_layer.group_send(
                f"user_messages_{participant_id}",
                {
                    "type": "message_update",
                    "update_type": "message_deleted_for_everyone",
                    "conversation_id": self.conversation_id,
                    "message_id": message_id,
                },
            )

    async def message_deleted_for_everyone_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_deleted_for_everyone",
                    "message_id": event["message_id"],
                    "conversation_id": event.get("conversation_id"),
                    "deleted_by": event.get("deleted_by"),
                }
            )
        )

    async def message_restored_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_restored",
                    "message_id": event["message_id"],
                    "conversation_id": event.get("conversation_id"),
                    "message": event.get("message"),
                }
            )
        )

    async def message_deleted_update(self, event):
        # Legacy hard-delete broadcast
        await self.send(
            text_data=json.dumps(
                {"type": "message_deleted", "message_id": event["message_id"]}
            )
        )

    async def chat_message(self, event):
        print("\033[95m=== Message reçu pour diffusion ===\033[0m")
        print(f"\033[95mÉvénement complet: {json.dumps(event, indent=2)}\033[0m")

        message_data = event.copy()
        message_type = message_data.pop("type")

        print(f"\033[95mType de message: {message_type}\033[0m")
        print(f"\033[95mDonnées à envoyer: {json.dumps(message_data, indent=2)}\033[0m")

        await self.send(text_data=json.dumps({"type": message_type, **message_data}))

    async def typing_update(self, event):
        # Ne pas renvoyer son propre typing
        if event.get("user_id") == self.scope["user"].id:
            return
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "user_id": event["user_id"],
                    "typing": event.get("typing", True),
                }
            )
        )

    async def message_status_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_status",
                    "message_ids": event.get("message_ids", []),
                    "status": event.get("status"),
                    "reader_id": event.get("reader_id"),
                    "timestamp": event.get("timestamp"),
                }
            )
        )

    async def presence_update_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event.get("user_id"),
                    "online": event.get("online"),
                }
            )
        )

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

    @database_sync_to_async
    def save_message(
        self,
        content=None,
        sender_id=None,
        files=None,
        job_offer_id=None,
        local_id=None,
        reply_to_id=None,
    ):
        try:
            print("\033[94m=== Sauvegarde du message et des médias ===\033[0m")
            conversation = Conversation.objects.get(id=self.conversation_id)

            from django.contrib.auth import get_user_model

            from .access import (
                WORKER_CANNOT_INITIATE,
                worker_blocked_from_first_message,
            )

            sender = get_user_model().objects.filter(pk=sender_id).first()
            if sender and worker_blocked_from_first_message(sender, conversation):
                return {
                    "error": True,
                    "code": "client_must_initiate",
                    "detail": WORKER_CANNOT_INITIATE,
                    "local_id": local_id,
                }

            reply_to = None
            if reply_to_id not in (None, "", "null", "undefined"):
                try:
                    reply_to = Message.objects.filter(
                        id=int(reply_to_id), conversation=conversation
                    ).first()
                except (TypeError, ValueError):
                    reply_to = None

            message = Message.objects.create(
                conversation=conversation,
                sender_id=sender_id,
                content=content,
                job_offer_id=job_offer_id,
                status="sent",
                reply_to=reply_to,
            )
            print(f"\033[94mMessage créé avec l'ID: {message.id}\033[0m")

            media_data = []
            if files:
                for file in files:
                    print(
                        f"\033[94mCréation du MessageMedia pour le fichier: {file.name}\033[0m"
                    )
                    media = MessageMedia.objects.create(message=message, file=file)
                    name = media.file.name.split("/")[-1] if media.file else ""
                    media_data.append(
                        {
                            "id": media.id,
                            "file": media.file.url if media.file else None,
                            "message": media.message.id,
                            "name": name,
                            "type": self._guess_mime_sync(name),
                        }
                    )
                    print(
                        f"\033[92mMessageMedia créé avec succès - URL: {media.file.url}\033[0m"
                    )

            reply_to_summary = None
            if message.reply_to_id:
                parent = message.reply_to
                sender = parent.sender
                sender_name = (
                    f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                    or getattr(sender, "username", "")
                    or str(sender.id)
                )
                reply_to_summary = {
                    "id": parent.id,
                    "content": None if parent.deleted_for_everyone else parent.content,
                    "sender": {"id": sender.id, "name": sender_name},
                    "has_media": parent.medias.exists()
                    and not parent.deleted_for_everyone,
                }

            message_data = {
                "id": message.id,
                "sender": sender_id,
                "sender_id": sender_id,
                "content": content,
                "medias": media_data,
                "timestamp": message.timestamp.isoformat(),
                "status": message.status,
                "edited_at": (
                    message.edited_at.isoformat() if message.edited_at else None
                ),
                "read_at": message.read_at.isoformat() if message.read_at else None,
                "job_offer": None,
                "local_id": local_id,
                "reply_to": reply_to_summary,
                "reply_to_id": message.reply_to_id,
            }

            print("\033[95m=== Données du message sauvegardé ===\033[0m")
            print(f"\033[95mMessage data: {json.dumps(message_data, indent=2)}\033[0m")

            return message_data
        except Conversation.DoesNotExist:
            print("\033[91mErreur: Conversation non trouvée\033[0m")
            raise PermissionDenied("Conversation non trouvée")
        except Exception as e:
            print(f"\033[91mErreur lors de la sauvegarde: {str(e)}\033[0m")
            raise

    @staticmethod
    def _guess_mime_sync(filename: str) -> str:
        lower = (filename or "").lower()
        if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic")):
            return "image/jpeg"
        if lower.endswith((".mp4", ".mov", ".avi", ".webm", ".m4v")):
            return "video/mp4"
        if lower.endswith((".mp3", ".wav", ".ogg", ".m4a", ".aac")):
            return "audio/m4a"
        if lower.endswith(".pdf"):
            return "application/pdf"
        return "application/octet-stream"
    @database_sync_to_async
    def get_job_offer_data(self, job_offer_id):
        from app_job.models import JobOffer
        from app_job.serializers import JobOfferSerializer

        try:
            print(f"\033[94mRécupération des données de l'offre {job_offer_id}\033[0m")
            job_offer = JobOffer.objects.get(id=job_offer_id)
            serializer = JobOfferSerializer(job_offer)
            # Convertir les données sérialisées en dictionnaire
            serialized_data = dict(serializer.data)
            print("\033[92mDonnées de l'offre récupérées avec succès\033[0m")
            return serialized_data
        except JobOffer.DoesNotExist:
            print(f"\033[91mErreur: Offre {job_offer_id} non trouvée\033[0m")
            return None
        except Exception as e:
            print(f"\033[91mErreur lors de la récupération de l'offre: {str(e)}\033[0m")
            return None

    @database_sync_to_async
    def mark_messages_as_read(self, conversation_id, user_id):
        messages = Message.objects.filter(
            conversation_id=conversation_id, status__in=["sent", "received"]
        ).exclude(sender_id=user_id)

        ids = list(messages.values_list("id", flat=True))
        now = timezone.now()
        for message in messages:
            message.status = "read"
            message.read_at = now
            message.save()

        from .models import ConversationMemberState

        ConversationMemberState.objects.filter(
            conversation_id=conversation_id, user_id=user_id
        ).update(marked_unread=False)
        return ids

    @database_sync_to_async
    def mark_messages_as_received(self, conversation_id, user_id):
        messages = Message.objects.filter(
            conversation_id=conversation_id, status="sent"
        ).exclude(sender_id=user_id)

        ids = list(messages.values_list("id", flat=True))
        for message in messages:
            message.status = "received"
            message.save(update_fields=["status"])
        return ids
    @database_sync_to_async
    def update_message(self, message_id, new_content, user_id):
        from django.contrib.auth import get_user_model

        from .message_visibility import can_edit

        User = get_user_model()
        try:
            message = Message.objects.get(
                id=message_id, sender_id=user_id, conversation_id=self.conversation_id
            )
            user = User.objects.get(id=user_id)
            if not can_edit(message, user):
                print(
                    f"\033[91mÉdition refusée pour message {message_id} (fenêtre ou droits)\033[0m"
                )
                return None
            message.content = new_content
            message.edited_at = timezone.now()
            message.save(update_fields=["content", "edited_at"])
            return message
        except Message.DoesNotExist:
            print(f"\033[91mErreur: Message {message_id} non trouvé\033[0m")
            return None

    @database_sync_to_async
    def hide_message_for_me(self, message_id, user_id):
        try:
            message = Message.objects.get(
                id=message_id, conversation_id=self.conversation_id
            )
            if not message.conversation.participants.filter(id=user_id).exists():
                return False
            message.hidden_for.add(user_id)
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def delete_message_for_everyone(self, message_id, user_id):
        from django.contrib.auth import get_user_model

        from .message_visibility import can_delete_for_everyone, mark_deleted_for_everyone

        User = get_user_model()
        try:
            message = Message.objects.get(
                id=message_id, conversation_id=self.conversation_id
            )
            user = User.objects.get(id=user_id)
            if not can_delete_for_everyone(message, user):
                return False
            mark_deleted_for_everyone(message)
            return True
        except Message.DoesNotExist:
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

        from .presence import presence_connect

        await database_sync_to_async(presence_connect)(self.user.id)

    async def disconnect(self, close_code):
        from .presence import presence_disconnect

        if hasattr(self, "user") and not self.user.is_anonymous:
            await database_sync_to_async(presence_disconnect)(self.user.id)
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def presence_update_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "user_id": event.get("user_id"),
                    "online": event.get("online"),
                }
            )
        )

    async def message_update(self, event):
        print("\033[95m=== Mise à jour de message reçue ===\033[0m")
        print(f"\033[95mType de mise à jour: {event['update_type']}\033[0m")
        print(f"\033[95mDonnées complètes: {json.dumps(event, indent=2)}\033[0m")

        update_type = event["update_type"]

        if update_type == "new_message":
            response_data = {
                "type": "new_message",
                "conversation_id": event["conversation_id"],
                "unread_count": event.get("unread_count", 0),
                "message": {
                    "id": event["message_id"],
                    "sender": event["sender_id"],
                    "content": event.get("content"),
                    "media_urls": event.get("media_urls", []),
                    "job_offer": event.get("job_offer"),
                    "timestamp": event["timestamp"],
                    "status": event["status"],
                },
            }
            print(
                f"\033[95mRéponse envoyée: {json.dumps(response_data, indent=2)}\033[0m"
            )
            await self.send(text_data=json.dumps(response_data))

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

        elif update_type == "message_deleted_for_everyone":
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "message_deleted_for_everyone",
                        "conversation_id": event["conversation_id"],
                        "message_id": event["message_id"],
                    }
                )
            )


class UnreadMessageStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close(code=403)
            return

        self.user_group_name = f"unread_status_{self.user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        from .presence import presence_connect

        await database_sync_to_async(presence_connect)(self.user.id)

        # Vérifier l'état initial des messages non lus
        has_unread = await self.check_unread_messages()
        await self.send_status_update(has_unread)

    async def disconnect(self, close_code):
        from .presence import presence_disconnect

        if hasattr(self, "user") and not self.user.is_anonymous:
            await database_sync_to_async(presence_disconnect)(self.user.id)
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """
        Gère les commandes reçues du client, notamment pour forcer une vérification
        """
        try:
            data = json.loads(text_data)
            if data.get("command") == "check_status":
                has_unread = await self.check_unread_messages()
                await self.send_status_update(has_unread)
        except json.JSONDecodeError:
            pass

    async def unread_status_update(self, event):
        """
        Reçoit les mises à jour des signaux et les transmet au client
        """
        await self.send_status_update(event["has_unread"])

    async def send_status_update(self, has_unread):
        """
        Méthode utilitaire pour envoyer les mises à jour au client
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "unread_status",
                    "has_unread": has_unread,
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    @database_sync_to_async
    def check_unread_messages(self):
        """
        Vérifie la présence de messages non lus dans toutes les conversations de l'utilisateur
        """
        return (
            Message.objects.filter(
                conversation__participants=self.user, status__in=["sent", "received"]
            )
            .exclude(sender=self.user)
            .exists()
        )
