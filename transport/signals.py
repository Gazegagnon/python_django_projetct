"""Signaux Django pour notifications automatiques."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TrackingEvent
from .notifications import notify_status_change

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TrackingEvent)
def send_email_on_tracking_event(sender, instance: TrackingEvent, created, **kwargs):
    """Notifie le client à chaque nouvel événement de tracking."""
    if not created:
        return
    expedition = instance.expedition
    try:
        notify_status_change(expedition, instance)
    except Exception:  # pragma: no cover
        logger.exception(
            "Notification post_save échouée pour %s",
            expedition.reference,
        )
