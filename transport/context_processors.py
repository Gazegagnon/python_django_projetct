from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from .models import Expedition

def admin_alerts(request):
    """
    Injecte des compteurs SLA/en attente dans toutes les pages.
    Visible surtout via la navbar (staff).
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    today = timezone.localdate()

    # seuil "en attente" (par défaut 3 jours, peut être overridé via querystring)
    alert_param = request.GET.get("alert_days", "3")
    try:
        alert_days = int(alert_param)
    except ValueError:
        alert_days = 3
    if alert_days < 1 or alert_days > 60:
        alert_days = 3

    threshold_date = today - timedelta(days=alert_days)

    overdue_count = Expedition.objects.filter(
        statut=Expedition.Statut.EN_ATTENTE,
        date_creation__date__lte=threshold_date
    ).count()

    sla_overdue_count = Expedition.objects.filter(
        date_cible__isnull=False,
        date_cible__lt=today
    ).exclude(statut=Expedition.Statut.LIVREE).count()

    return {
        "nav_alert_days": alert_days,
        "nav_overdue_count": overdue_count,
        "nav_sla_overdue_count": sla_overdue_count,
    }