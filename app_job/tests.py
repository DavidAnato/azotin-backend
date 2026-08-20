from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from app_job.models import Category, JobOffer
from app_job.search import expand_search_query, has_only_urgency_keywords
from app_profile.models import ClientProfile

User = get_user_model()


class SearchHelperTests(APITestCase):
    def test_expand_includes_french_english_synonyms(self):
        terms = [t.lower() for t in expand_search_query("plombier ménage")]
        self.assertTrue(any("plumber" in t or t == "plumber" for t in terms))
        self.assertTrue(any("cleaning" in t or t == "cleaning" for t in terms))

    def test_expand_covers_seed_trades_and_urgency(self):
        tile_terms = [t.lower() for t in expand_search_query("carrelage")]
        self.assertTrue(any(t in ("tile", "carreleur", "tiler") for t in tile_terms))
        moving = [t.lower() for t in expand_search_query("déménagement")]
        self.assertTrue(any("moving" in t or t == "moving" for t in moving))
        self.assertTrue(has_only_urgency_keywords(["urgent"]))
        self.assertFalse(has_only_urgency_keywords(["plombier", "urgent"]))

    def test_job_search_query_params(self):
        user = User.objects.create_user(
            phone_number="22971110001",
            password="testpass123",
            first_name="Client",
            last_name="Test",
            email="c7111@test.local",
            profile_type="employer",
            kyc_status="approved",
        )
        ClientProfile.objects.get_or_create(user=user)
        cat = Category.objects.create(name="Plomberie", description="d")
        JobOffer.objects.create(
            title="Plombier à domicile",
            description="Réparation robinet",
            location="Cotonou",
            price=10000,
            client=user.client_profile,
            category=cat,
            is_urgent=True,
            deadline="2026-09-01",
        )
        JobOffer.objects.create(
            title="Jardinage",
            description="Tondre la pelouse",
            location="Porto-Novo",
            price=5000,
            client=user.client_profile,
            is_urgent=False,
            deadline="2026-12-01",
        )
        res = self.client.get("/job/job-search/", {"query": "plumber", "urgent": "true"})
        self.assertEqual(res.status_code, 200)
        results = res.data["results"] if isinstance(res.data, dict) else res.data
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("match_score", results[0])
        self.assertTrue(results[0]["is_urgent"])
        titles = [item["title"] for item in results]
        self.assertTrue(any("Plombier" in t for t in titles))
        self.assertFalse(any("Jardinage" in t for t in titles))

        res_alias = self.client.get("/job/job-search/", {"is_urgent": "true"})
        self.assertEqual(res_alias.status_code, 200)
        alias_results = (
            res_alias.data["results"]
            if isinstance(res_alias.data, dict)
            else res_alias.data
        )
        self.assertTrue(all(item["is_urgent"] for item in alias_results))

        res_urgent_query = self.client.get("/job/job-search/", {"query": "urgent"})
        self.assertEqual(res_urgent_query.status_code, 200)
        urgent_results = (
            res_urgent_query.data["results"]
            if isinstance(res_urgent_query.data, dict)
            else res_urgent_query.data
        )
        self.assertGreaterEqual(len(urgent_results), 1)
        self.assertTrue(all(item["is_urgent"] for item in urgent_results))

        res_deadline = self.client.get(
            "/job/job-search/", {"deadline_before": "2026-09-15"}
        )
        self.assertEqual(res_deadline.status_code, 200)
        deadline_results = (
            res_deadline.data["results"]
            if isinstance(res_deadline.data, dict)
            else res_deadline.data
        )
        self.assertTrue(any("Plombier" in item["title"] for item in deadline_results))
        self.assertFalse(any("Jardinage" in item["title"] for item in deadline_results))

        res_from = self.client.get("/job/job-search/", {"deadline_from": "2026-11-01"})
        self.assertEqual(res_from.status_code, 200)
        from_results = (
            res_from.data["results"] if isinstance(res_from.data, dict) else res_from.data
        )
        self.assertTrue(any("Jardinage" in item["title"] for item in from_results))
        self.assertFalse(any("Plombier" in item["title"] for item in from_results))
