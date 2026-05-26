"""Vues dashboard staff scindées par fonctionnalité."""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from .models import Expedition
from .services import (
    expedition_kpis,
    expedition_sla_row,
    expedition_waiting_row,
    get_page,
    pagination_context,
)


def _parse_days(request, default=30):
    try:
        days = int(request.GET.get("days", str(default)))
    except ValueError:
        days = default
    return days if days in (7, 30, 90) else default


def _parse_alert_days(request, default=3):
    try:
        alert_days = int(request.GET.get("alert_days", str(default)))
    except ValueError:
        alert_days = default
    return alert_days if 1 <= alert_days <= 60 else default


@staff_member_required
def dashboard_overview(request):
    """KPI + graphiques uniquement."""
    today = timezone.localdate()
    days_selected = _parse_days(request)

    start = today - timedelta(days=days_selected - 1)
    kpi_data = expedition_kpis()
    statut_map = kpi_data["statut_map"]
    statut_labels = [label for _, label in Expedition.Statut.choices]
    statut_keys = [key for key, _ in Expedition.Statut.choices]
    statut_values = [statut_map.get(k, 0) for k in statut_keys]

    per_day_qs = (
        Expedition.objects.filter(date_creation__date__gte=start, date_creation__date__lte=today)
        .annotate(day=TruncDate("date_creation"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    per_day_map = {row["day"]: row["n"] for row in per_day_qs}
    day_list = [start + timedelta(days=i) for i in range(days_selected)]

    return render(
        request,
        "transport/dashboard_overview.html",
        {
            "days_selected": days_selected,
            "total": kpi_data["total"],
            "kpis": kpi_data,
            "statut_labels_json": json.dumps(statut_labels),
            "statut_values_json": json.dumps(statut_values),
            "per_day_labels_json": json.dumps([d.isoformat() for d in day_list]),
            "per_day_values_json": json.dumps([per_day_map.get(d, 0) for d in day_list]),
        },
    )


@staff_member_required
def dashboard_alertes(request):
    """Alertes opérationnelles et SLA."""
    today = timezone.localdate()
    days_selected = _parse_days(request)
    alert_days = _parse_alert_days(request)
    threshold_date = today - timedelta(days=alert_days)

    sla_qs = (
        Expedition.objects.filter(date_cible__isnull=False, date_cible__lt=today)
        .exclude(statut=Expedition.Statut.LIVREE)
        .order_by("date_cible")
    )
    overdue_qs = (
        Expedition.objects.filter(
            statut=Expedition.Statut.EN_ATTENTE,
            date_creation__date__lte=threshold_date,
        )
        .order_by("date_creation")
    )

    sla_page = get_page(request, sla_qs, per_page=15)
    overdue_page = get_page(request, overdue_qs, per_page=15)

    ctx = {
        "days_selected": days_selected,
        "alert_days": alert_days,
        "sla_overdue_count": sla_qs.count(),
        "overdue_count": overdue_qs.count(),
        "sla_list": [expedition_sla_row(e, today) for e in sla_page],
        "overdue_list": [expedition_waiting_row(e, today) for e in overdue_page],
    }
    ctx.update(pagination_context(sla_page))
    ctx["sla_page_obj"] = sla_page
    ctx["overdue_page_obj"] = overdue_page
    return render(request, "transport/dashboard_alertes.html", ctx)


@staff_member_required
def dashboard_activite(request):
    """Dernières expéditions et top destinations."""
    latest = Expedition.objects.select_related("client_user").order_by("-date_creation")[:20]
    top_destinations = (
        Expedition.objects.values("destination")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )
    return render(
        request,
        "transport/dashboard_activite.html",
        {
            "latest_expeditions": latest,
            "top_destinations": top_destinations,
        },
    )
