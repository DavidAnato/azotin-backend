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
        "conversations/<int:pk>/restore/",
        views.ConversationRestoreView.as_view(),
        name="conversation-restore",
    ),
    path(
        "conversations/<int:pk>/archive/",
        views.ConversationArchiveView.as_view(),
        name="conversation-archive",
    ),
    path(
        "conversations/<int:pk>/mute/",
        views.ConversationMuteView.as_view(),
        name="conversation-mute",
    ),
    path(
        "conversations/<int:pk>/mark-unread/",
        views.ConversationMarkUnreadView.as_view(),
        name="conversation-mark-unread",
    ),
    path(
        "conversations/create/",
        views.ConversationCreateView.as_view(),
        name="conversation-create",
    ),
    path("messages/", views.MessageListView.as_view(), name="message-list"),
    path(
        "messages/create/",
        views.MessageCreateView.as_view(),
        name="message-create",
    ),
    path(
        "messages/<int:pk>/delete/",
        views.MessageDeleteView.as_view(),
        name="message-delete",
    ),
    path(
        "messages/<int:pk>/restore/",
        views.MessageRestoreView.as_view(),
        name="message-restore",
    ),
    path(
        "messages/mark-as-read/",
        views.MarkMessagesAsReadView.as_view(),
        name="mark-messages-read",
    ),
]
