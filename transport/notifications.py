"""Service d'envoi de notifications email.

En développement, ``EMAIL_BACKEND`` est positionné sur la console : les emails
s'affichent dans le terminal. En production, configurer SMTP via les variables
``EMAIL_HOST`` / ``EMAIL_HOST_USER`` / ``EMAIL_HOST_PASSWORD``.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_status_change(expedition, event) -> bool:
    """Envoie un email au client lorsqu'un nouvel événement est enregistré.

    Renvoie ``True`` si une tentative d'envoi a été faite, ``False`` sinon
    (par exemple si l'expédition n'a pas d'email destinataire).
    """
    recipient = expedition.client_email or (
        expedition.client_user.email if expedition.client_user_id else ""
    )
    if not recipient:
        return False

    subject = f"[Transport] {expedition.reference} — {event.get_statut_display()}"
    body = (
        f"Bonjour {expedition.client_nom or 'client'},\n\n"
        f"Le statut de votre expédition {expedition.reference} vient de changer.\n"
        f"Nouveau statut : {event.get_statut_display()}\n"
        f"{('Détail : ' + event.commentaire) if event.commentaire else ''}\n\n"
        f"Origine : {expedition.origine}\n"
        f"Destination : {expedition.destination}\n\n"
        "Cordialement,\n"
        "L'équipe Transport Console."
    )

    try:
        sent = send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.info(
            "Notification envoyée pour %s (statut=%s) à %s",
            expedition.reference,
            event.statut,
            recipient,
        )
        return bool(sent)
    except Exception:  # pragma: no cover — on log mais on ne casse jamais la requête
        logger.exception(
            "Échec d'envoi de notification pour %s (statut=%s)",
            expedition.reference,
            event.statut,
        )
        return False
