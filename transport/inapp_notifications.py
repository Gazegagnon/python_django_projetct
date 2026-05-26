"""Notifications in-app (centre de messages staff / client)."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from .models import Expedition, Notification

User = get_user_model()


def create_notification(
    *,
    destinataire,
    categorie: str,
    titre: str,
    message: str,
    lien: str = "",
    expedition: Expedition | None = None,
) -> Notification:
    return Notification.objects.create(
        destinataire=destinataire,
        categorie=categorie,
        titre=titre,
        message=message,
        lien=lien,
        expedition=expedition,
    )


def notify_staff(
    *,
    categorie: str,
    titre: str,
    message: str,
    lien: str = "",
    expedition: Expedition | None = None,
) -> int:
    """Notifie tous les comptes staff actifs."""
    count = 0
    for user in User.objects.filter(is_staff=True, is_active=True):
        create_notification(
            destinataire=user,
            categorie=categorie,
            titre=titre,
            message=message,
            lien=lien,
            expedition=expedition,
        )
        count += 1
    return count


def notify_expedition_client(
    *,
    expedition: Expedition,
    categorie: str,
    titre: str,
    message: str,
    lien: str = "",
) -> Notification | None:
    """Notifie le client propriétaire d'une expédition."""
    if not expedition.client_user_id:
        return None
    return create_notification(
        destinataire=expedition.client_user,
        categorie=categorie,
        titre=titre,
        message=message,
        lien=lien or f"/client/commandes/{expedition.reference}/",
        expedition=expedition,
    )


def unread_count_for(user) -> int:
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(destinataire=user, lu=False).count()
