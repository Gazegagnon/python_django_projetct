"""Tests de non-régression couvrant les corrections de sécurité et le workflow."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Expedition, Livraison, TrackingEvent, Vehicule
from .services import should_notify_tracking_event


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

    def test_payload_includes_livraison_statut(self):
        vehicule = Vehicule.objects.create(immatriculation="XY-999-ZZ")
        Livraison.objects.create(
            expedition=self.expedition,
            vehicule=vehicule,
            statut=Livraison.Statut.EN_COURS,
        )
        self.client.login(username="bob", password="pwd12345!")
        data = self.client.get(self.url).json()
        self.assertEqual(data["livraison_statut"], Livraison.Statut.EN_COURS)

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


class LivraisonFinishReleaseVehiculeTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="ops2", password="pwd12345!", is_staff=True
        )
        self.expedition = Expedition.objects.create()
        self.vehicule = Vehicule.objects.create(
            immatriculation="FR-123-AB",
            statut=Vehicule.Statut.EN_MISSION,
        )
        self.livraison = Livraison.objects.create(
            expedition=self.expedition,
            vehicule=self.vehicule,
            statut=Livraison.Statut.EN_COURS,
        )

    def test_finish_remet_vehicule_disponible(self):
        self.client.login(username="ops2", password="pwd12345!")
        response = self.client.post(
            reverse("livraison_finish", args=[self.expedition.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.vehicule.refresh_from_db()
        self.livraison.refresh_from_db()
        self.expedition.refresh_from_db()
        self.assertEqual(self.vehicule.statut, Vehicule.Statut.DISPONIBLE)
        self.assertEqual(self.livraison.statut, Livraison.Statut.TERMINEE)
        self.assertEqual(self.expedition.statut, Expedition.Statut.LIVREE)


class ClientCancelLivraisonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="marc", password="pwd12345!")
        self.expedition = Expedition.objects.create(client_user=self.user)
        self.vehicule = Vehicule.objects.create(
            immatriculation="PL-456-CD",
            statut=Vehicule.Statut.EN_MISSION,
        )
        self.livraison = Livraison.objects.create(
            expedition=self.expedition,
            vehicule=self.vehicule,
            statut=Livraison.Statut.PLANIFIEE,
        )

    def test_annulation_libere_livraison_et_vehicule(self):
        self.client.login(username="marc", password="pwd12345!")
        url = reverse("client_commande_cancel", args=[self.expedition.reference])
        response = self.client.post(url, {"raison_annulation": "Report"})
        self.assertEqual(response.status_code, 302)
        self.livraison.refresh_from_db()
        self.vehicule.refresh_from_db()
        self.assertEqual(self.livraison.statut, Livraison.Statut.ANNULEE)
        self.assertEqual(self.vehicule.statut, Vehicule.Statut.DISPONIBLE)


class SuiviNotFoundTests(TestCase):
    def test_reference_inconnue_retourne_200(self):
        response = self.client.get(
            reverse("suivi_expedition"),
            {"reference": "EXP-2099-9999"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune expédition trouvée")


class ExpeditionExportCsvTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="export", password="pwd12345!", is_staff=True
        )
        self.client_user = User.objects.create_user(
            username="buyer", password="pwd12345!"
        )
        Expedition.objects.create(
            client_nom="Alice",
            client_email="alice@example.com",
            origine="Paris",
            destination="Lyon",
            client_user=self.client_user,
        )

    def test_staff_peut_exporter_csv(self):
        self.client.login(username="export", password="pwd12345!")
        response = self.client.get(reverse("expedition_export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode("utf-8-sig")
        self.assertIn("reference", body)
        self.assertIn("Alice", body)

    def test_client_ne_peut_pas_exporter(self):
        self.client.login(username="buyer", password="pwd12345!")
        response = self.client.get(reverse("expedition_export_csv"))
        self.assertEqual(response.status_code, 302)


class SignupTests(TestCase):
    def test_inscription_cree_compte_et_connecte(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "nouveau",
                "email": "nouveau@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="nouveau").exists())
        self.assertRedirects(response, reverse("home"))


class ExpeditionPositionThrottlingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="throttle", password="pwd12345!")
        self.expedition = Expedition.objects.create(client_user=self.owner)
        self.url = reverse("expedition_position", args=[self.expedition.reference])
        cache.clear()

    def test_trop_de_requetes_retourne_429(self):
        self.client.login(username="throttle", password="pwd12345!")
        key = f"rl:expedition_position:user:{self.owner.pk}"
        cache.set(key, 120, 3600)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many requests", response.json()["detail"])


class ShouldNotifyTrackingEventTests(TestCase):
    def test_skip_creation_et_modification_client(self):
        exp = Expedition.objects.create()
        creation = TrackingEvent(
            expedition=exp,
            statut=Expedition.Statut.EN_ATTENTE,
            commentaire="Commande créée par le client.",
        )
        modification = TrackingEvent(
            expedition=exp,
            statut=Expedition.Statut.EN_ATTENTE,
            commentaire="Commande modifiée par le client.",
        )
        normal = TrackingEvent(
            expedition=exp,
            statut=Expedition.Statut.EN_COURS,
            commentaire="Livraison démarrée.",
        )
        self.assertFalse(should_notify_tracking_event(creation))
        self.assertFalse(should_notify_tracking_event(modification))
        self.assertTrue(should_notify_tracking_event(normal))


class PlanifierLivraisonReplanTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="planner", password="pwd12345!", is_staff=True
        )
        self.expedition = Expedition.objects.create(statut=Expedition.Statut.EN_ATTENTE)
        self.vehicule = Vehicule.objects.create(immatriculation="PL-001-AA")
        self.livraison = Livraison.objects.create(
            expedition=self.expedition,
            vehicule=self.vehicule,
            statut=Livraison.Statut.ANNULEE,
        )

    def test_replanifier_reutilise_livraison_existante(self):
        v2 = Vehicule.objects.create(immatriculation="PL-002-BB")
        self.client.login(username="planner", password="pwd12345!")
        url = reverse("planifier_livraison", args=[self.expedition.pk])
        response = self.client.post(
            url,
            {"vehicule": v2.pk, "date_depart": "2026-06-01T10:00"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Livraison.objects.filter(expedition=self.expedition).count(), 1)
        self.livraison.refresh_from_db()
        self.expedition.refresh_from_db()
        self.assertEqual(self.livraison.vehicule_id, v2.pk)
        self.assertEqual(self.livraison.statut, Livraison.Statut.PLANIFIEE)
        self.assertEqual(self.expedition.statut, Expedition.Statut.EN_COURS)
