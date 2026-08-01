from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<conversation_id>\w+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/messages/$", consumers.MessageListConsumer.as_asgi()),
    re_path(r"ws/messages-status/$", consumers.UnreadMessageStatusConsumer.as_asgi()),
]
