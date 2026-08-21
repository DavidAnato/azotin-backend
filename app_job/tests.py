from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from app_job.models import Category, JobOffer, SubCategory
from app_job.search import expand_search_query, has_only_urgency_keywords
from app_profile.models import ClientProfile, WorkerProfile

User = get_user_model()


def _norm_terms(query: str):
    return {_strip_for_test(t) for t in expand_search_query(query)}


def _strip_for_test(token: str) -> str:
    import unicodedata
    import re

    token = unicodedata.normalize("NFD", token.lower().strip())
    token = "".join(c for c in token if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", token)


class SearchHelperTests(APITestCase):
    def test_expand_includes_french_english_synonyms(self):
        terms = [t.lower() for t in expand_search_query("plombier ménage")]
        self.assertTrue(any("plumber" in t or t == "plumber" for t in terms))
        self.assertTrue(any("cleaning" in t or t == "cleaning" for t in terms))

    def test_trade_and_activity_are_bidirectional(self):
        pairs = (
            ("plombier", "plomberie"),
            ("électricien", "électricité"),
            ("peintre", "peinture"),
            ("menager", "ménage"),
            ("carreleur", "carrelage"),
            ("jardinier", "jardinage"),
            ("menuisier", "menuiserie"),
            ("coiffeur", "coiffure"),
            ("soudeur", "soudure"),
            ("maçon", "maçonnerie"),
            ("cuisinier", "cuisine"),
            ("livreur", "livraison"),
        )
        for trade, activity in pairs:
            trade_terms = _norm_terms(trade)
            activity_terms = _norm_terms(activity)
            self.assertIn(
                _strip_for_test(activity),
                trade_terms,
                f"{trade!r} devrait produire {activity!r}, obtenu {sorted(trade_terms)}",
            )
            self.assertIn(
                _strip_for_test(trade),
                activity_terms,
                f"{activity!r} devrait produire {trade!r}, obtenu {sorted(activity_terms)}",
            )

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
            is_certified=True,
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

    def test_plombier_query_matches_plomberie_category(self):
        user = User.objects.create_user(
            phone_number="22971110002",
            password="testpass123",
            first_name="Client",
            last_name="Plomb",
            email="c7112@test.local",
            profile_type="employer",
            is_certified=True,
        )
        ClientProfile.objects.get_or_create(user=user)
        cat = Category.objects.create(name="Bâtiment", description="d")
        sub = SubCategory.objects.create(
            name="Plomberie", description="d", category=cat
        )
        JobOffer.objects.create(
            title="Fuite salle de bain",
            description="Réparer le robinet",
            location="Cotonou",
            price=8000,
            client=user.client_profile,
            category=cat,
            sub_category=sub,
        )
        JobOffer.objects.create(
            title="Tonte pelouse",
            description="Jardin",
            location="Cotonou",
            price=4000,
            client=user.client_profile,
        )
        res = self.client.get("/job/job-search/", {"query": "plombier"})
        self.assertEqual(res.status_code, 200)
        results = res.data["results"] if isinstance(res.data, dict) else res.data
        titles = [item["title"] for item in results]
        self.assertTrue(any("Fuite" in t for t in titles))
        self.assertFalse(any("Tonte" in t for t in titles))

        res_rev = self.client.get("/job/job-search/", {"query": "plomberie"})
        self.assertEqual(res_rev.status_code, 200)
        rev_results = (
            res_rev.data["results"] if isinstance(res_rev.data, dict) else res_rev.data
        )
        self.assertTrue(any("Fuite" in item["title"] for item in rev_results))

    def test_worker_search_expands_trade_to_job_types(self):
        client = User.objects.create_user(
            phone_number="22971110003",
            password="testpass123",
            first_name="Client",
            last_name="Search",
            email="c7113@test.local",
            profile_type="employer",
            is_certified=True,
        )
        ClientProfile.objects.get_or_create(user=client)
        worker = User.objects.create_user(
            phone_number="22971110004",
            password="testpass123",
            first_name="Koffi",
            last_name="Plombs",
            email="w7114@test.local",
            profile_type="worker",
            is_certified=True,
        )
        other = User.objects.create_user(
            phone_number="22971110005",
            password="testpass123",
            first_name="Awa",
            last_name="Jardin",
            email="w7115@test.local",
            profile_type="worker",
            is_certified=True,
        )
        cat = Category.objects.create(name="Bâtiment", description="d")
        plumbing = SubCategory.objects.create(
            name="Plomberie", description="d", category=cat
        )
        garden = SubCategory.objects.create(
            name="Jardinage", description="d", category=cat
        )
        plumber_profile, _ = WorkerProfile.objects.get_or_create(user=worker)
        plumber_profile.title = plumbing
        plumber_profile.skills = "Installation sanitaire"
        plumber_profile.save()
        plumber_profile.job_types.set([plumbing])
        gardener_profile, _ = WorkerProfile.objects.get_or_create(user=other)
        gardener_profile.title = garden
        gardener_profile.save()
        gardener_profile.job_types.set([garden])

        self.client.force_authenticate(client)
        res = self.client.get(
            "/profile/worker-profile-search/", {"query": "plombier"}
        )
        self.assertEqual(res.status_code, 200)
        results = res.data["results"] if isinstance(res.data, dict) else res.data
        worker_ids = [item["id"] for item in results]
        self.assertIn(plumber_profile.id, worker_ids)
        self.assertNotIn(gardener_profile.id, worker_ids)
