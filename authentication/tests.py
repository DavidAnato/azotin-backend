from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from app_job.models import Category, SubCategory
from app_profile.models import ClientProfile, WorkerProfile
from authentication.otp_service import otp_service_ready, send_otp, verify_otp

User = get_user_model()


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
        user.kyc_status = "approved"
        user.is_certified = True
        user.save()
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
    def test_submit_and_block_offer_until_approved(self):
        user = _make_user("22970000011")
        self.client.force_authenticate(user)
        get_res = self.client.get("/authentication/kyc/")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.data["kyc_status"], "none")

        post_res = self.client.post(
            "/authentication/kyc/",
            {"id_type": "cni", "id_number": "AB123"},
            format="json",
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.data["kyc_status"], "pending")

        cat = Category.objects.create(name="Plomberie", description="d")
        sub = SubCategory.objects.create(name="Fuite", description="d", category=cat)
        offer_res = self.client.post(
            "/job/job-offers/",
            {
                "title": "Réparer fuite",
                "description": "Cuisine",
                "location": "Cotonou",
                "price": 15000,
                "sub_category": sub.id,
            },
            format="json",
        )
        self.assertEqual(offer_res.status_code, 403)
        self.assertEqual(offer_res.data.get("code"), "kyc_required")

        user.kyc_status = "approved"
        user.save()
        offer_res2 = self.client.post(
            "/job/job-offers/",
            {
                "title": "Réparer fuite",
                "description": "Cuisine",
                "location": "Cotonou",
                "price": 15000,
                "sub_category": sub.id,
            },
            format="json",
        )
        self.assertEqual(offer_res2.status_code, status.HTTP_201_CREATED)

    def test_certified_user_is_approved(self):
        user = _make_user("22970000012")
        user.is_certified = True
        user.save()
        self.client.force_authenticate(user)
        res = self.client.get("/authentication/kyc/")
        self.assertEqual(res.data["kyc_status"], "approved")


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

    @override_settings(OTP_SKIP_SMS=False, OURVOICE_API_KEY="gov-test-key")
    @patch("authentication.otp_service.requests.post")
    def test_send_otp_sends_api_key_header_without_app_id(self, mock_post):
        mock_resp = mock_post.return_value
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True}
        mock_resp.raise_for_status.return_value = None
        ok, _ = send_otp("22970000112", api_key="gov-test-key")
        self.assertTrue(ok)
        payload = mock_post.call_args.kwargs["json"]
        headers = mock_post.call_args.kwargs["headers"]
        self.assertNotIn("app_id", payload)
        self.assertEqual(payload.get("send_to"), "22970000112")
        self.assertEqual(headers.get("Authorization"), "Bearer gov-test-key")


class EmailActivateUrlTests(APITestCase):
    def test_email_activate_url_name(self):
        self.assertEqual(reverse("email-activate"), "/authentication/email-activate/")
