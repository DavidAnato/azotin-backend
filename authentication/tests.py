import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from app_job.models import Category, SubCategory
from app_profile.models import ClientProfile, WorkerProfile
from authentication.models import KycSubmission
from authentication.otp_service import otp_service_ready, send_otp, verify_otp

User = get_user_model()


def _set_kyc(user, status, *, full_name=""):
    submission, _ = KycSubmission.objects.update_or_create(
        user=user,
        defaults={
            "status": status,
            "full_name": full_name
            or f"{user.first_name} {user.last_name or ''}".strip(),
            "submitted_at": timezone.now() if status != "none" else None,
            "reviewed_at": timezone.now()
            if status in ("approved", "rejected")
            else None,
        },
    )
    return submission


def _make_user(phone, *, profile_type="employer", **kwargs):
    user = User.objects.create_user(
        phone_number=phone,
        password="testpass123",
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        email=kwargs.get("email", f"{phone}@test.local"),
        profile_type=profile_type,
    )
    if kwargs.get("kyc_approved"):
        _set_kyc(user, "approved")
        user.refresh_from_db()
    if profile_type == "worker":
        WorkerProfile.objects.get_or_create(user=user)
    else:
        ClientProfile.objects.get_or_create(user=user)
    return user


class DeleteAccountTests(APITestCase):
    def test_soft_delete_current_user_only(self):
        user = _make_user("22970000001")
        other = _make_user("22970000002", first_name="Other")
        self.client.force_authenticate(user)
        refresh = RefreshToken.for_user(user)
        res = self.client.post(
            "/authentication/delete-account/",
            {"refresh_token": str(refresh)},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(user.email.startswith("deleted+"))
        self.assertTrue(other.is_active)
        self.assertNotIn("access", res.data)
        self.assertNotIn("refresh", res.data)
        self.assertNotEqual(other.phone_number, user.phone_number)


class KYCTests(APITestCase):
    def _create_subcategory(self):
        cat = Category.objects.create(name="Plomberie", description="d")
        return SubCategory.objects.create(name="Fuite", description="d", category=cat)

    def _post_offer(self, sub_id):
        return self.client.post(
            "/job/job-offers/",
            {
                "title": "Réparer fuite",
                "description": "Cuisine",
                "location": "Cotonou",
                "price": 15000,
                "sub_category": sub_id,
            },
            format="json",
        )

    def test_submit_and_block_offer_until_approved(self):
        user = _make_user("22970000011")
        self.client.force_authenticate(user)
        get_res = self.client.get("/authentication/kyc/")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.data["kyc_status"], "none")

        sub = self._create_subcategory()
        none_res = self._post_offer(sub.id)
        self.assertEqual(none_res.status_code, 403)
        self.assertEqual(none_res.data.get("code"), "kyc_required")

        post_res = self.client.post(
            "/authentication/kyc/",
            {"id_type": "cni", "id_number": "AB123", "full_name": "Ada Lovelace"},
            format="json",
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.data["kyc_status"], "pending")
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Ada")
        self.assertEqual(user.last_name, "Lovelace")

        offer_res = self._post_offer(sub.id)
        self.assertEqual(offer_res.status_code, 403)
        self.assertEqual(offer_res.data.get("code"), "kyc_pending")

        _set_kyc(user, "approved")
        user.refresh_from_db()
        offer_res2 = self._post_offer(sub.id)
        self.assertEqual(offer_res2.status_code, status.HTTP_201_CREATED)

        offer_res3 = self._post_offer(sub.id)
        self.assertEqual(offer_res3.status_code, status.HTTP_201_CREATED)

    def test_never_submitted_blocks_create_and_apply(self):
        employer = _make_user("22970000021", kyc_approved=True)
        worker = _make_user("22970000022", profile_type="worker")
        cat = Category.objects.create(name="Jardinage", description="d")
        sub = SubCategory.objects.create(name="Tonte", description="d", category=cat)
        self.client.force_authenticate(employer)
        offer = self.client.post(
            "/job/job-offers/",
            {
                "title": "Tondre pelouse",
                "description": "Jardin",
                "location": "Cotonou",
                "price": 8000,
                "sub_category": sub.id,
            },
            format="json",
        )
        self.assertEqual(offer.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(worker)
        apply_res = self.client.post(
            f"/job/job-offers/{offer.data['id']}/applications/",
            {"proposed_price": 9000, "cover_letter": "Je peux le faire"},
            format="json",
        )
        self.assertEqual(apply_res.status_code, 403)
        self.assertEqual(apply_res.data.get("code"), "kyc_required")

        _set_kyc(worker, "pending")
        worker.refresh_from_db()
        apply_pending = self.client.post(
            f"/job/job-offers/{offer.data['id']}/applications/",
            {"proposed_price": 9000, "cover_letter": "Je peux le faire"},
            format="json",
        )
        self.assertEqual(apply_pending.status_code, 403)
        self.assertEqual(apply_pending.data.get("code"), "kyc_pending")

        _set_kyc(worker, "approved")
        worker.refresh_from_db()
        apply_ok = self.client.post(
            f"/job/job-offers/{offer.data['id']}/applications/",
            {"proposed_price": 9000, "cover_letter": "Je peux le faire"},
            format="json",
        )
        self.assertEqual(apply_ok.status_code, status.HTTP_201_CREATED)

    def test_certified_user_is_approved(self):
        user = _make_user("22970000012")
        user.is_certified = True
        user.save()
        self.client.force_authenticate(user)
        res = self.client.get("/authentication/kyc/")
        self.assertEqual(res.data["kyc_status"], "approved")
        me = self.client.get("/authentication/user-profile/")
        self.assertEqual(me.data["user"]["kyc_status"], "approved")

    def test_submit_piece_and_selfie_stays_pending(self):
        user = _make_user("22970000013")
        self.client.force_authenticate(user)

        def _png(name):
            buf = io.BytesIO()
            Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
            return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

        res = self.client.post(
            "/authentication/kyc/",
            {
                "full_name": "Ada Lovelace",
                "piece": _png("id.png"),
                "selfie": _png("selfie.png"),
            },
            format="multipart",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["kyc_status"], "pending")
        self.assertTrue(res.data["has_id_document"])
        self.assertTrue(res.data["has_selfie"])
        user.refresh_from_db()
        submission = user.kyc_submission
        self.assertTrue(submission.id_document)
        self.assertTrue(submission.selfie)
        self.assertEqual(submission.status, "pending")
        self.assertFalse(user.is_certified)


class OTPConfigTests(APITestCase):
    @override_settings(OTP_SKIP_SMS=False, OURVOICE_API_KEY="", GETOURVOICE_API_KEY="")
    def test_register_returns_503_when_keys_missing(self):
        res = self.client.post(
            "/authentication/register/",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone_number": "22970000999",
                "profile_type": "employer",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(res.data.get("code"), "otp_service_unavailable")

    @override_settings(OTP_SKIP_SMS=True, DEV_OTP_CODE="00000")
    def test_dev_otp_bypass_still_works(self):
        res = self.client.post(
            "/authentication/register/",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone_number": "22970000998",
                "profile_type": "employer",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data.get("dev_otp"), "00000")

    @override_settings(
        OTP_SKIP_SMS=False,
        OURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="",
    )
    def test_ready_with_api_key_only(self):
        self.assertTrue(otp_service_ready())

    @override_settings(OTP_SKIP_SMS=True)
    def test_skip_sms_does_not_need_api_key(self):
        ok, payload = send_otp("22970000111", api_key="")
        self.assertTrue(ok)
        self.assertEqual(payload.get("dev_otp"), "00000")
        ok, payload = verify_otp("22970000111", "00000", api_key="")
        self.assertTrue(ok)

    @override_settings(
        OTP_SKIP_SMS=False,
        OURVOICE_API_KEY="",
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="",
    )
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_matches_official_docs(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.text = '{"data": {"status": "pending"}}'
        mock_resp.json.return_value = {"data": {"status": "pending"}}
        ok, _ = send_otp("22970000112")
        self.assertTrue(ok)
        url = mock_post.call_args.args[0]
        payload = mock_post.call_args.kwargs["json"]
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(url, "https://api.getourvoice.com/v1/otp/send")
        self.assertNotIn("app_id", payload)
        self.assertNotIn("app_name", payload)
        self.assertEqual(payload.get("send_to"), "22970000112")
        self.assertEqual(payload.get("channel"), "sms")
        self.assertNotIn("to", payload)
        self.assertNotIn("phone", payload)
        self.assertNotIn("via", payload)
        self.assertNotIn("provider", payload)
        self.assertEqual(headers.get("Authorization"), "Bearer gov-test-key")
        self.assertEqual(headers.get("Accept"), "application/json")
        self.assertNotIn("X-Api-Key", headers)

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="088421fe-00c6-11ef-9fe5-7f2e687d3db8",
        GETOURVOICE_APP_NAME="should-not-be-sent",
    )
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_includes_app_id_not_both(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "pending"}}
        ok, _ = send_otp("+229 70 00 01 12")
        self.assertTrue(ok)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload.get("send_to"), "22970000112")
        self.assertEqual(
            payload.get("app_id"), "088421fe-00c6-11ef-9fe5-7f2e687d3db8"
        )
        self.assertNotIn("app_name", payload)
        self.assertEqual(payload.get("channel"), "sms")

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="Azɔbatɛn",
    )
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_uses_app_name_when_no_app_id(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "pending"}}
        ok, _ = send_otp("22970000112")
        self.assertTrue(ok)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload.get("app_name"), "Azɔbatɛn")
        self.assertNotIn("app_id", payload)
        self.assertEqual(payload.get("channel"), "sms")

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="",
    )
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_422_exposes_api_details_without_key(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 422
        mock_resp.text = '{"message":"The app_id field is required."}'
        ok, payload = send_otp("22970000112")
        self.assertFalse(ok)
        self.assertIn("app_id", payload.get("details", ""))
        self.assertNotIn("gov-test-key", str(payload))

    @override_settings(
        OTP_SKIP_SMS=False,
        OURVOICE_API_KEY="",
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="app-uuid",
        GETOURVOICE_APP_NAME="",
    )
    @patch("authentication.otp_service.requests.post")
    def test_verify_otp_matches_official_docs(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "valid": True,
            "data": {"status": "verified"},
        }
        ok, _ = verify_otp("+22970000112", "12345")
        self.assertTrue(ok)
        url = mock_post.call_args.args[0]
        payload = mock_post.call_args.kwargs["json"]
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(url, "https://api.getourvoice.com/v1/otp/verify")
        self.assertEqual(payload.get("send_to"), "22970000112")
        self.assertEqual(payload.get("code"), "12345")
        self.assertEqual(payload.get("app_id"), "app-uuid")
        self.assertNotIn("app_name", payload)
        self.assertEqual(headers.get("Authorization"), "Bearer gov-test-key")
        self.assertNotIn("X-Api-Key", headers)

    @override_settings(OTP_SKIP_SMS=True, DEV_OTP_CODE="00000")
    @patch("authentication.otp_service.requests.post")
    def test_skip_sms_skips_getourvoice(self, mock_post):
        ok, payload = send_otp("22970000111")
        self.assertTrue(ok)
        self.assertEqual(payload.get("dev_otp"), "00000")
        self.assertEqual(payload.get("channel"), "sms")
        mock_post.assert_not_called()

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="Azɔbatɛn",
    )
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_sms_channel(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "pending", "channel": "sms"}}
        ok, _ = send_otp("22970000112", channel="sms")
        self.assertTrue(ok)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload.get("channel"), "sms")
        self.assertEqual(payload.get("app_name"), "Azɔbatɛn")
        self.assertNotIn("app_id", payload)

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="Azɔbatɛn",
    )
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_whatsapp_forced_to_sms(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": {"status": "pending", "channel": "sms"}}
        ok, _ = send_otp("22970000112", channel="whatsapp")
        self.assertTrue(ok)
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload.get("channel"), "sms")
        self.assertEqual(payload.get("app_name"), "Azɔbatɛn")
        self.assertNotIn("app_id", payload)
        self.assertNotIn("via", payload)
        self.assertNotIn("provider", payload)

    def test_send_otp_rejects_invalid_channel(self):
        ok, payload = send_otp("22970000112", channel="voice")
        self.assertFalse(ok)
        self.assertIn("sms", payload.get("error", ""))

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="Azɔbatɛn",
    )
    @patch("authentication.views.send_otp")
    def test_register_ignores_whatsapp_channel(self, mock_send):
        mock_send.return_value = (True, {"data": {"channel": "sms"}})
        res = self.client.post(
            "/authentication/register/",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone_number": "22970000991",
                "profile_type": "employer",
                "channel": "whatsapp",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data.get("channel"), "sms")
        self.assertEqual(mock_send.call_args.kwargs.get("channel"), "sms")

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="Azɔbatɛn",
    )
    @patch("authentication.views.send_otp")
    def test_register_defaults_to_sms_channel(self, mock_send):
        mock_send.return_value = (True, {"data": {"channel": "sms"}})
        res = self.client.post(
            "/authentication/register/",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone_number": "22970000992",
                "profile_type": "employer",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data.get("channel"), "sms")
        self.assertEqual(mock_send.call_args.kwargs.get("channel"), "sms")

    def test_register_rejects_invalid_channel(self):
        res = self.client.post(
            "/authentication/register/",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "phone_number": "22970000993",
                "profile_type": "employer",
                "channel": "telegram",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("channel", res.data)

    @override_settings(
        OTP_SKIP_SMS=False,
        GETOURVOICE_API_KEY="gov-test-key",
        GETOURVOICE_APP_ID="",
        GETOURVOICE_APP_NAME="Azɔbatɛn",
    )
    @patch("authentication.views.send_otp")
    def test_phone_validate_request_uses_sms_and_ignores_whatsapp(self, mock_send):
        mock_send.return_value = (True, {"data": {"status": "pending"}})
        user = _make_user("22970000994")
        sms_res = self.client.post(
            "/authentication/phone-number-validate-request/",
            {"phone_number": user.phone_number, "channel": "sms"},
            format="json",
        )
        self.assertEqual(sms_res.status_code, status.HTTP_200_OK)
        self.assertEqual(sms_res.data.get("channel"), "sms")
        self.assertEqual(mock_send.call_args.kwargs.get("channel"), "sms")

        wa_res = self.client.post(
            "/authentication/phone-number-validate-request/",
            {"phone_number": user.phone_number, "channel": "whatsapp"},
            format="json",
        )
        self.assertEqual(wa_res.status_code, status.HTTP_200_OK)
        self.assertEqual(wa_res.data.get("channel"), "sms")
        self.assertEqual(mock_send.call_args.kwargs.get("channel"), "sms")


class EmailActivateUrlTests(APITestCase):
    def test_email_activate_url_name(self):
        self.assertEqual(reverse("email-activate"), "/authentication/email-activate/")


class EmailVerificationTests(APITestCase):
    def setUp(self):
        self.user = _make_user("22970000401")
        self.user.verified_email = False
        self.user.save(update_fields=["verified_email"])

    def test_request_sends_azobatin_activation_email(self):
        res = self.client.post(
            "/authentication/email-validate-request/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        from django.core import mail

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Azobatin", message.subject)
        self.user.refresh_from_db()
        self.assertIn(self.user.otp_code, message.body)
        self.assertIn("Activer mon compte", message.alternatives[0][0])
        self.assertIn("email-activate", message.body)

    def test_authenticated_request_uses_user_email(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(
            "/authentication/email-validate-request/",
            {},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        from django.core import mail

        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_already_verified_is_rejected(self):
        self.user.verified_email = True
        self.user.save(update_fields=["verified_email"])
        res = self.client.post(
            "/authentication/email-validate-request/",
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(FRONTEND_URL="https://app.azobatin.test")
    def test_get_activate_redirects_and_marks_verified(self):
        self.user.otp_code = "12345"
        self.user.otp_generated_at = timezone.now()
        self.user.save(update_fields=["otp_code", "otp_generated_at"])
        res = self.client.get(
            "/authentication/email-activate/",
            {"otp_code": "12345", "email": self.user.email},
        )
        self.assertEqual(res.status_code, status.HTTP_302_FOUND)
        self.assertEqual(
            res["Location"], "https://app.azobatin.test/activation-success"
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.verified_email)
        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.otp_code)

    def test_post_activate_with_invalid_otp(self):
        self.user.otp_code = "12345"
        self.user.otp_generated_at = timezone.now()
        self.user.save(update_fields=["otp_code", "otp_generated_at"])
        res = self.client.post(
            "/authentication/email-activate/",
            {"email": self.user.email, "otp_code": "00000"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.verified_email)
