"""Logique métier partagée (workflow livraison, pagination, alertes)."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count, Q

from .models import Expedition, Livraison, Vehicule


def get_page(request, queryset, *, per_page: int = 10):
    """Retourne une page paginée à partir du paramètre GET ``page``."""
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def pagination_context(page_obj):
    return {
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
    }


def release_vehicule(vehicule: Vehicule) -> None:
    """Remet un véhicule au statut disponible."""
    if vehicule.statut != Vehicule.Statut.DISPONIBLE:
        vehicule.statut = Vehicule.Statut.DISPONIBLE
        vehicule.save(update_fields=["statut"])


def cancel_livraison_for_expedition(expedition: Expedition) -> None:
    """Annule la livraison liée et libère le véhicule si besoin."""
    liv = getattr(expedition, "livraison", None)
    if not liv or liv.statut == Livraison.Statut.ANNULEE:
        return
    vehicule = liv.vehicule
    was_active = liv.statut in (
        Livraison.Statut.PLANIFIEE,
        Livraison.Statut.EN_COURS,
    )
    liv.statut = Livraison.Statut.ANNULEE
    liv.save(update_fields=["statut"])
    if was_active:
        release_vehicule(vehicule)


def expedition_sla_row(expedition: Expedition, today) -> dict:
    return {
        "pk": expedition.pk,
        "reference": expedition.reference,
        "client_nom": expedition.client_nom,
        "origine": expedition.origine,
        "destination": expedition.destination,
        "date_cible": expedition.date_cible,
        "days_late": (today - expedition.date_cible).days,
    }


def expedition_waiting_row(expedition: Expedition, today) -> dict:
    return {
        "pk": expedition.pk,
        "reference": expedition.reference,
        "client_nom": expedition.client_nom,
        "origine": expedition.origine,
        "destination": expedition.destination,
        "days_waiting": (today - expedition.date_creation.date()).days,
    }


def expedition_kpis() -> dict[str, int]:
    """Agrège les KPI par statut en une seule requête."""
    rows = (
        Expedition.objects.values("statut")
        .annotate(n=Count("id"))
    )
    statut_map = {row["statut"]: row["n"] for row in rows}
    return {
        "total": sum(statut_map.values()),
        "en_attente": statut_map.get(Expedition.Statut.EN_ATTENTE, 0),
        "en_cours": statut_map.get(Expedition.Statut.EN_COURS, 0),
        "livree": statut_map.get(Expedition.Statut.LIVREE, 0),
        "annulee": statut_map.get(Expedition.Statut.ANNULEE, 0),
        "statut_map": statut_map,
    }


def filter_expeditions_queryset(qs, *, q: str = "", statut: str = ""):
    """Filtre une queryset expédition (recherche multi-champs + statut)."""
    if q:
        qs = qs.filter(
            Q(reference__icontains=q)
            | Q(client_nom__icontains=q)
            | Q(client_email__icontains=q)
            | Q(origine__icontains=q)
            | Q(destination__icontains=q)
        )
    if statut:
        qs = qs.filter(statut=statut)
    return qs


def should_notify_tracking_event(event) -> bool:
    """Évite d'envoyer un email pour la création initiale de commande."""
    if event.commentaire == "Commande créée par le client.":
        return False
    if event.commentaire == "Commande modifiée par le client.":
        return False
    return True


def vehicule_stat_counts() -> dict[str, int]:
    return {
        "total": Vehicule.objects.count(),
        "disponible": Vehicule.objects.filter(statut=Vehicule.Statut.DISPONIBLE).count(),
        "en_mission": Vehicule.objects.filter(statut=Vehicule.Statut.EN_MISSION).count(),
        "maintenance": Vehicule.objects.filter(statut=Vehicule.Statut.MAINTENANCE).count(),
    }


def assign_livraison_planifiee(
    *,
    expedition: Expedition,
    vehicule: Vehicule,
    date_depart,
    existing: Livraison | None = None,
) -> Livraison:
    """Crée ou met à jour la livraison planifiée (OneToOne par expédition)."""
    if existing and existing.statut in (
        Livraison.Statut.PLANIFIEE,
        Livraison.Statut.EN_COURS,
    ):
        raise ValueError("Livraison déjà active.")

    if existing and existing.statut in (
        Livraison.Statut.ANNULEE,
        Livraison.Statut.TERMINEE,
    ):
        old_vehicule = existing.vehicule
        if old_vehicule.pk != vehicule.pk and not old_vehicule.livraison_active:
            release_vehicule(old_vehicule)
        existing.vehicule = vehicule
        existing.date_depart = date_depart
        existing.statut = Livraison.Statut.PLANIFIEE
        existing.date_arrivee = None
        existing.lat = None
        existing.lng = None
        existing.position_maj = None
        existing.save()
        livraison = existing
    else:
        livraison = Livraison.objects.create(
            expedition=expedition,
            vehicule=vehicule,
            date_depart=date_depart,
            statut=Livraison.Statut.PLANIFIEE,
        )

    vehicule.statut = Vehicule.Statut.EN_MISSION
    vehicule.save(update_fields=["statut"])

    expedition.statut = Expedition.Statut.EN_COURS
    expedition.save(update_fields=["statut"])

    return livraison
