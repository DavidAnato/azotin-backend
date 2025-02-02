import json
from django.utils import timezone
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import PermissionDenied

from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        if self.scope["user"].is_anonymous:
            await self.close(code=403)
            return

        is_participant = await self.is_conversation_participant()
        if not is_participant:
            await self.close(code=403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action_type = data.get("type", "message")

            if action_type == "message":
                await self.handle_new_message(data)
            elif action_type == "mark_read":
                await self.handle_mark_read(data)
            elif action_type == "edit":
                await self.handle_edit_message(data)
            elif action_type == "delete":
                await self.handle_delete_message(data)

        except (KeyError, json.JSONDecodeError):
            pass
        except Exception as e:
            print(f"[ChatConsumer] Error in receive: {e}")
            await self.close()

    async def handle_new_message(self, data):
        message = data["message"]
        sender_id = self.scope["user"].id

        if not message.strip():
            return

        saved_message = await self.save_message(message, sender_id)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender_id": sender_id,
                "timestamp": saved_message.timestamp.isoformat(),
                "message_id": saved_message.id,
            }
        )

        conversation_participants = await self.get_conversation_participants()
        for participant_id in conversation_participants:
            unread_count = await self.get_unread_count(participant_id, self.conversation_id)
            await self.channel_layer.group_send(
                f"user_messages_{participant_id}",
                {
                    "type": "message_update",
                    "update_type": "new_message",
                    "conversation_id": self.conversation_id,
                    "message_id": saved_message.id,
                    "sender_id": sender_id,
                    "content": message,
                    "timestamp": saved_message.timestamp.isoformat(),
                    "status": "sent",
                    "unread_count": unread_count
                }
            )

    async def handle_mark_read(self, data):
        conversation_id = self.conversation_id
        user_id = self.scope["user"].id
        
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
                    "timestamp": timezone.now().isoformat()
                }
            )

    async def handle_edit_message(self, data):
        message_id = data["message_id"]
        new_content = data["content"]
        user_id = self.scope["user"].id

        # Get the old content before updating
        old_content = await self.get_message_content(message_id)
        updated_message = await self.update_message(message_id, new_content, user_id)
        
        if updated_message:
            # Notify chat room participants about the edit
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited_update",
                    "message_id": message_id,
                    "content": new_content,
                    "edited_at": updated_message.edited_at.isoformat()
                }
            )
            
            # Check if this is the last message in the conversation
            is_last = await self.is_last_message(message_id)
            print(f"[ChatConsumer] Message édité {message_id} est le dernier message: {is_last}")
            if is_last:
                conversation_participants = await self.get_conversation_participants()
                for participant_id in conversation_participants:
                    unread_count = await self.get_unread_count(participant_id, self.conversation_id)
                    await self.channel_layer.group_send(
                        f"user_messages_{participant_id}",
                        {
                            "type": "message_update",
                            "update_type": "message_edited",
                            "conversation_id": self.conversation_id,
                            "old_content": old_content,
                            "content": new_content,
                            "edited_at": updated_message.edited_at.isoformat(),
                            "unread_count": unread_count
                        }
                    )

    async def handle_delete_message(self, data):
        message_id = data["message_id"]
        user_id = self.scope["user"].id

        # Check if it's the last message before deleting
        is_last = await self.is_last_message(message_id)
        print(f"[ChatConsumer] Message supprimé {message_id} est le dernier message: {is_last}")
        new_last_message = None
        
        if is_last:
            # Get the previous message before deletion
            new_last_message = await self.get_previous_message(message_id)
            print(f"[ChatConsumer] Nouveau dernier message après suppression: {new_last_message.id if new_last_message else 'Aucun'}")

        if await self.delete_message(message_id, user_id):
            # Notify chat room participants about the deletion
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_deleted_update",
                    "message_id": message_id
                }
            )
            
            if is_last:
                conversation_participants = await self.get_conversation_participants()
                for participant_id in conversation_participants:
                    unread_count = await self.get_unread_count(participant_id, self.conversation_id)
                    message_data = {
                        "type": "message_update",
                        "update_type": "message_deleted",
                        "conversation_id": self.conversation_id,
                        "message_id": message_id,
                        "unread_count": unread_count
                    }
                    
                    if new_last_message:
                        message_data["new_last_message"] = {
                            "content": new_last_message.content,
                            "timestamp": new_last_message.timestamp.isoformat()
                        }
                    
                    await self.channel_layer.group_send(
                        f"user_messages_{participant_id}",
                        message_data
                    )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": event["message"],
            "sender_id": event["sender_id"],
            "timestamp": event["timestamp"],
            "message_id": event["message_id"]
        }))

    async def messages_read_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "messages_read",
            "reader_id": event["reader_id"],
            "timestamp": event["timestamp"]
        }))

    async def message_edited_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_edited", 
            "message_id": event["message_id"],
            "content": event["content"],
            "edited_at": event["edited_at"]
        }))

    async def message_deleted_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_deleted",
            "message_id": event["message_id"]
        }))

    @database_sync_to_async
    def save_message(self, content, sender_id):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            message = Message.objects.create(
                conversation=conversation,
                sender_id=sender_id,
                content=content,
                status="sent",
            )
            return message
        except Conversation.DoesNotExist:
            raise PermissionDenied("Conversation non trouvée")

    @database_sync_to_async
    def mark_messages_as_read(self, conversation_id, user_id):
        Message.objects.filter(
            conversation_id=conversation_id,
            status__in=['sent', 'received']
        ).exclude(
            sender_id=user_id
        ).update(
            status='read',
            read_at=timezone.now()
        )

    @database_sync_to_async
    def update_message(self, message_id, new_content, user_id):
        try:
            message = Message.objects.get(
                id=message_id,
                sender_id=user_id,
                conversation_id=self.conversation_id
            )
            message.content = new_content
            message.edited_at = timezone.now()
            message.save()
            return message
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_message(self, message_id, user_id):
        try:
            message = Message.objects.get(
                id=message_id,
                sender_id=user_id,
                conversation_id=self.conversation_id
            )
            message.delete()
            return True
        except Message.DoesNotExist:
            return False

    @database_sync_to_async
    def is_conversation_participant(self):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.participants.filter(id=self.scope["user"].id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def get_conversation_participants(self):
        conversation = Conversation.objects.get(id=self.conversation_id)
        return list(conversation.participants.values_list('id', flat=True))

    @database_sync_to_async
    def is_last_message(self, message_id):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            last_message = conversation.messages.order_by('-timestamp').first()
            
            print(f"[ChatConsumer] Type message_id: {type(message_id)}")
            print(f"[ChatConsumer] Type last_message.id: {type(last_message.id if last_message else None)}")
            
            # Conversion explicite en str pour la comparaison
            message_id_str = str(message_id)
            last_message_id_str = str(last_message.id) if last_message else None
            
            is_last = last_message and message_id_str == last_message_id_str
            
            print(f"[ChatConsumer] Dernier message de la conversation: {last_message_id_str}")
            print(f"[ChatConsumer] Message à vérifier: {message_id_str}")
            print(f"[ChatConsumer] Comparaison: {last_message_id_str} == {message_id_str}")
            print(f"[ChatConsumer] Résultat de la comparaison: {is_last}")
            
            return is_last
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def get_message_content(self, message_id):
        try:
            message = Message.objects.get(id=message_id)
            return message.content
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def get_previous_message(self, message_id):
        try:
            current_message = Message.objects.get(id=message_id)
            return Message.objects.filter(
                conversation_id=self.conversation_id,
                timestamp__lt=current_message.timestamp
            ).order_by('-timestamp').first()
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def get_unread_count(self, user_id, conversation_id):
        return Message.objects.filter(
            conversation_id=conversation_id,
            status__in=['sent', 'received'],
            conversation__participants=user_id
        ).exclude(sender_id=user_id).count()




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
        print(f"[MessageListConsumer] Message update reçu - Type: {update_type}")
        
        if update_type == "new_message":
            await self.send(text_data=json.dumps({
                "type": "new_message",
                "conversation_id": event["conversation_id"],
                "unread_count": event.get("unread_count", 0),
                "message": {
                    "id": event["message_id"],
                    "sender": event["sender_id"],
                    "content": event["content"],
                    "timestamp": event["timestamp"],
                    "status": event["status"]
                }
            }))
        
        elif update_type == "messages_read":
            await self.send(text_data=json.dumps({
                "type": "messages_read",
                "conversation_id": event["conversation_id"],
                "reader_id": event["reader_id"],
                "timestamp": event["timestamp"],
                "unread_count": 0
            }))
        
        elif update_type == "message_edited":
            await self.send(text_data=json.dumps({
                "type": "message_edited",
                "conversation_id": event["conversation_id"],
                "unread_count": event.get("unread_count", 0),
                "message_id": event["message_id"],
                "content": event["content"],
                "edited_at": event["edited_at"]
            }))
        
        elif update_type == "message_deleted":
            response_data = {
                "type": "message_deleted",
                "conversation_id": event["conversation_id"],
                "unread_count": event.get("unread_count", 0),
                "message_id": event["message_id"]
            }
            
            if "new_last_message" in event:
                response_data["new_last_message"] = event["new_last_message"]
                
            await self.send(text_data=json.dumps(response_data))