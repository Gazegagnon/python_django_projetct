from datetime import timedelta

from django.utils import timezone

from .inapp_notifications import unread_count_for
from .models import Expedition


def admin_alerts(request):
    """
    Injecte des compteurs SLA/en attente (staff) et notifications non lues.
    """
    ctx = {}
    if request.user.is_authenticated:
        ctx["nav_unread_notifications"] = unread_count_for(request.user)

    if not request.user.is_authenticated or not request.user.is_staff:
        return ctx

    today = timezone.localdate()
    alert_param = request.GET.get("alert_days", "3")
    try:
        alert_days = int(alert_param)
    except ValueError:
        alert_days = 3
    if alert_days < 1 or alert_days > 60:
        alert_days = 3

    threshold_date = today - timedelta(days=alert_days)

    ctx.update({
        "nav_alert_days": alert_days,
        "nav_overdue_count": Expedition.objects.filter(
            statut=Expedition.Statut.EN_ATTENTE,
            date_creation__date__lte=threshold_date,
        ).count(),
        "nav_sla_overdue_count": Expedition.objects.filter(
            date_cible__isnull=False,
            date_cible__lt=today,
        ).exclude(statut=Expedition.Statut.LIVREE).count(),
    })
    return ctx
