from django.contrib.auth import get_user_model
from unittest.mock import patch

from rest_framework.test import APITestCase

from app_profile.models import ClientProfile, WorkerProfile

User = get_user_model()


def _make_user(phone, profile_type):
    user = User.objects.create_user(
        phone_number=phone,
        password="testpass123",
        first_name=profile_type.title(),
        last_name="Test",
        email=f"{phone}@test.local",
        profile_type=profile_type,
    )
    if profile_type == "worker":
        WorkerProfile.objects.get_or_create(user=user)
    else:
        ClientProfile.objects.get_or_create(user=user)
    return user


class MessagingInitiationTests(APITestCase):
    def setUp(self):
        self.client_user = _make_user("22972000001", "employer")
        self.worker = _make_user("22972000002", "worker")

    def test_worker_cannot_create_new_conversation(self):
        self.client.force_authenticate(self.worker)
        res = self.client.post(
            f"/messaging/conversations/create/?participant_id={self.client_user.id}"
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data.get("code"), "client_must_initiate")

    @patch("app_messaging.views.broadcast_new_message")
    def test_client_starts_then_both_can_reply(self, _broadcast):
        self.client.force_authenticate(self.client_user)
        create_res = self.client.post(
            f"/messaging/conversations/create/?participant_id={self.worker.id}"
        )
        self.assertEqual(create_res.status_code, 201)
        conv_id = create_res.data["id"]

        self.client.force_authenticate(self.worker)
        first_worker = self.client.post(
            "/messaging/messages/create/",
            {"conversation_id": conv_id, "content": "Salut"},
            format="json",
        )
        self.assertEqual(first_worker.status_code, 403)

        self.client.force_authenticate(self.client_user)
        first_client = self.client.post(
            "/messaging/messages/create/",
            {"conversation_id": conv_id, "content": "Bonjour"},
            format="json",
        )
        self.assertEqual(first_client.status_code, 201)

        self.client.force_authenticate(self.worker)
        reply = self.client.post(
            "/messaging/messages/create/",
            {"conversation_id": conv_id, "content": "Je suis dispo"},
            format="json",
        )
        self.assertEqual(reply.status_code, 201)

        self.client.force_authenticate(self.worker)
        existing = self.client.post(
            f"/messaging/conversations/create/?participant_id={self.client_user.id}"
        )
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.data["id"], conv_id)
