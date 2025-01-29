from django.urls import path

from . import views

app_name = "app_messaging"

urlpatterns = [
    path(
        "conversations/", views.ConversationListView.as_view(), name="conversation-list"
    ),
    path(
        "conversations/<int:pk>/",
        views.ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/create/",
        views.ConversationCreateView.as_view(),
        name="conversation-create",
    ),
    path("messages/", views.MessageListView.as_view(), name="message-list"),
    path(
        "messages/mark-as-read/",
        views.MarkMessagesAsReadView.as_view(),
        name="mark-messages-read",
    ),
]
