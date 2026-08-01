import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import UserNotification


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_authenticated:
            self.room_group_name = f"notifications_{self.user.id}"

            # Rejoindre le groupe de notification
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Quitter le groupe
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        command = data.get("command")

        if command == "mark_as_read":
            notification_id = data.get("notification_id")
            await self.mark_notification_as_read(notification_id)

        elif command == "get_notifications":
            await self.send_notifications()

    async def notification(self, event):
        # Envoyer la notification au WebSocket
        await self.send(
            text_data=json.dumps(
                {"type": "notification", "notification": event["notification"]}
            )
        )

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        try:
            UserNotification.objects.filter(
                id=notification_id, recipient=self.user
            ).update(is_read=True)
        except UserNotification.DoesNotExist:
            pass

    @database_sync_to_async
    def get_notifications(self):
        return list(
            UserNotification.objects.filter(recipient=self.user, is_read=False).values(
                "id", "message", "object", "created_at"
            )
        )


class NotificationStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Définir le nom du groupe unique pour l'utilisateur
        self.user_group_name = f"notification_status_{self.user.id}"

        # Rejoindre le groupe
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        # Envoyer le statut initial
        has_unread = await self.has_unread_notifications()
        await self.send_status_update(has_unread)

    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

    async def notification_status_update(self, event):
        """Reçoit les mises à jour des signaux"""
        await self.send_status_update(event["has_unread"])

    async def send_status_update(self, has_unread):
        """Méthode utilitaire pour envoyer les mises à jour"""
        await self.send(
            text_data=json.dumps(
                {"type": "notification_status", "has_unread": has_unread}
            )
        )

    @database_sync_to_async
    def has_unread_notifications(self):
        return UserNotification.objects.filter(
            recipient=self.user, is_read=False
        ).exists()
