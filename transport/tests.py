"""Tests de non-régression couvrant les corrections de sécurité et le workflow."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Expedition, Livraison, TrackingEvent, Vehicule


User = get_user_model()


class ExpeditionReferenceTests(TestCase):
    def test_reference_auto_generee(self):
        exp1 = Expedition.objects.create()
        exp2 = Expedition.objects.create()
        self.assertTrue(exp1.reference.startswith("EXP-"))
        self.assertNotEqual(exp1.reference, exp2.reference)
        self.assertEqual(exp2.numero, exp1.numero + 1)


class StaffCbvSecurityTests(TestCase):
    """Vérifie que les CBV Expedition* refusent les utilisateurs non staff."""

    def setUp(self):
        self.client_user = User.objects.create_user(username="alice", password="pwd12345!")
        self.staff_user = User.objects.create_user(
            username="admin", password="pwd12345!", is_staff=True
        )
        self.expedition = Expedition.objects.create()

    def _assert_redirects_to_login(self, response):
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_anonymous_cannot_list(self):
        self._assert_redirects_to_login(self.client.get(reverse("expedition_list")))

    def test_authenticated_non_staff_is_forbidden_on_list(self):
        self.client.login(username="alice", password="pwd12345!")
        response = self.client.get(reverse("expedition_list"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_list(self):
        self.client.login(username="admin", password="pwd12345!")
        response = self.client.get(reverse("expedition_list"))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_cannot_create(self):
        self._assert_redirects_to_login(self.client.get(reverse("expedition_create")))

    def test_anonymous_cannot_delete(self):
        url = reverse("expedition_delete", args=[self.expedition.pk])
        self._assert_redirects_to_login(self.client.get(url))


class LivraisonActionsRequirePostTests(TestCase):
    """livraison_start / livraison_finish / livraison_demo_position : POST + staff."""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="ops", password="pwd12345!", is_staff=True
        )
        self.expedition = Expedition.objects.create()
        self.vehicule = Vehicule.objects.create(immatriculation="AB-001-CD")
        self.livraison = Livraison.objects.create(
            expedition=self.expedition,
            vehicule=self.vehicule,
        )

    def test_get_is_rejected(self):
        self.client.login(username="ops", password="pwd12345!")
        response = self.client.get(reverse("livraison_start", args=[self.expedition.pk]))
        self.assertEqual(response.status_code, 405)

    def test_post_demarre_livraison(self):
        self.client.login(username="ops", password="pwd12345!")
        response = self.client.post(reverse("livraison_start", args=[self.expedition.pk]))
        self.assertEqual(response.status_code, 302)
        self.expedition.refresh_from_db()
        self.livraison.refresh_from_db()
        self.assertEqual(self.expedition.statut, Expedition.Statut.EN_COURS)
        self.assertEqual(self.livraison.statut, Livraison.Statut.EN_COURS)
        self.assertIsNotNone(self.livraison.date_depart)
        self.assertTrue(
            TrackingEvent.objects.filter(expedition=self.expedition).exists()
        )


class ExpeditionPositionApiTests(TestCase):
    """L'API position exige authentification et restreint aux ayants droit."""

    def setUp(self):
        self.owner = User.objects.create_user(username="bob", password="pwd12345!")
        self.intruder = User.objects.create_user(username="eve", password="pwd12345!")
        self.staff = User.objects.create_user(
            username="root", password="pwd12345!", is_staff=True
        )
        self.expedition = Expedition.objects.create(client_user=self.owner)
        self.url = reverse("expedition_position", args=[self.expedition.reference])

    def test_anonymous_is_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_other_user_is_forbidden(self):
        self.client.login(username="eve", password="pwd12345!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_owner_can_read(self):
        self.client.login(username="bob", password="pwd12345!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["has_position"])

    def test_staff_can_read(self):
        self.client.login(username="root", password="pwd12345!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_orphan_expedition_requires_staff(self):
        """Une expédition sans client_user ne doit pas leaker sa position à un client lambda."""
        orphan = Expedition.objects.create()
        url = reverse("expedition_position", args=[orphan.reference])
        self.client.login(username="eve", password="pwd12345!")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class ClientCommandeCancelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="claire", password="pwd12345!")
        self.expedition = Expedition.objects.create(client_user=self.user)

    def test_client_peut_annuler_sa_commande_en_attente(self):
        self.client.login(username="claire", password="pwd12345!")
        url = reverse("client_commande_cancel", args=[self.expedition.reference])
        response = self.client.post(url, {"raison_annulation": "Changement de plan"})
        self.assertEqual(response.status_code, 302)
        self.expedition.refresh_from_db()
        self.assertEqual(self.expedition.statut, Expedition.Statut.ANNULEE)
        self.assertEqual(self.expedition.raison_annulation, "Changement de plan")
