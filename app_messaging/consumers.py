import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        # Rejoindre le groupe de conversation
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Quitter le groupe de conversation
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data["message"]
        sender_id = self.scope["user"].id

        # Sauvegarder le message dans la base de données
        saved_message = await self.save_message(message, sender_id)

        # Envoyer le message au groupe de conversation
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender_id": sender_id,
                "timestamp": saved_message.timestamp.isoformat(),
                "message_id": saved_message.id,
            },
        )

    async def chat_message(self, event):
        # Envoyer le message au WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "sender_id": event["sender_id"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                }
            )
        )

    @database_sync_to_async
    def save_message(self, content, sender_id):
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender_id=sender_id,
            content=content,
            status="sent",
        )
        return message
