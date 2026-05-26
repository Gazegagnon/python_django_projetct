from datetime import timedelta
import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .client_forms import ClientCommandeCreateForm, ClientCommandeUpdateForm
from .forms import ExpeditionForm
from .livraison_forms import PlanifierLivraisonForm
from .models import Expedition, Livraison, TrackingEvent, Vehicule


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restreint l'accès aux membres du staff (compatible avec les CBV)."""

    def test_func(self):
        return self.request.user.is_active and self.request.user.is_staff


def home(request):
    return render(request, "transport/home.html")


class ExpeditionListView(StaffRequiredMixin, ListView):
    model = Expedition
    template_name = "transport/expedition_list.html"
    context_object_name = "expeditions"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().select_related("client_user", "livraison__vehicule")
        q = self.request.GET.get("q")
        statut = self.request.GET.get("statut")
        if q:
            qs = qs.filter(reference__icontains=q)
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        ctx["current_q"] = self.request.GET.get("q", "")
        ctx["current_statut"] = self.request.GET.get("statut", "")
        ctx["statut_choices"] = Expedition.Statut.choices
        return ctx


class ExpeditionDetailView(StaffRequiredMixin, DetailView):
    model = Expedition
    template_name = "transport/expedition_detail.html"
    context_object_name = "expedition"

    def get_queryset(self):
        return super().get_queryset().select_related("client_user", "livraison__vehicule")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["events"] = self.object.events.all()
        return ctx


class ExpeditionCreateView(StaffRequiredMixin, CreateView):
    model = Expedition
    form_class = ExpeditionForm
    template_name = "transport/expedition_form.html"
    success_url = reverse_lazy("expedition_list")


class ExpeditionUpdateView(StaffRequiredMixin, UpdateView):
    model = Expedition
    form_class = ExpeditionForm
    template_name = "transport/expedition_form.html"
    success_url = reverse_lazy("expedition_list")


class ExpeditionDeleteView(StaffRequiredMixin, DeleteView):
    model = Expedition
    template_name = "transport/expedition_confirm_delete.html"
    success_url = reverse_lazy("expedition_list")


def suivi_expedition(request):
    expedition = None
    events = None
    reference = request.GET.get("reference")

    if reference:
        expedition = get_object_or_404(Expedition, reference=reference)
        events = expedition.events.all()

    return render(
        request,
        "transport/suivi.html",
        {
            "expedition": expedition,
            "events": events,
            "reference": reference,
        },
    )

@login_required
def expedition_position(request, reference):
    exp = get_object_or_404(Expedition, reference=reference)

    is_staff = request.user.is_staff
    is_owner = exp.client_user_id is not None and exp.client_user_id == request.user.id
    if not (is_staff or is_owner):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    liv = getattr(exp, "livraison", None)
    if not liv or liv.lat is None or liv.lng is None:
        return JsonResponse({
            "reference": exp.reference,
            "has_position": False,
            "lat": None,
            "lng": None,
            "updated_at": None,
            "statut": exp.statut,
        })

    return JsonResponse({
        "reference": exp.reference,
        "has_position": True,
        "lat": float(liv.lat),
        "lng": float(liv.lng),
        "updated_at": liv.position_maj.isoformat() if liv.position_maj else None,
        "statut": exp.statut,
    })


@staff_member_required
def dashboard(request):
    # ---------------------------
    # Période dynamique : 7/30/90
    # ---------------------------
    today = timezone.localdate()
    days_param = request.GET.get("days", "30")
    try:
        days_selected = int(days_param)
    except ValueError:
        days_selected = 30

    if days_selected not in (7, 30, 90):
        days_selected = 30

    start = today - timedelta(days=days_selected - 1)

    # ---------------------------
    # Alert SLA : expéditions en retard (date_cible dépassée)
    # ---------------------------
    sla_qs = (
        Expedition.objects
        .filter(date_cible__isnull=False, date_cible__lt=today)
        .exclude(statut=Expedition.Statut.LIVREE)
        .order_by("date_cible")
    )

    sla_overdue_count = sla_qs.count()

    sla_overdue_list = []
    for e in sla_qs[:5]:
        sla_overdue_list.append({
            "pk": e.pk,
            "reference": e.reference,
            "client_nom": e.client_nom,
            "origine": e.origine,
            "destination": e.destination,
            "date_cible": e.date_cible,
            "days_late": (today - e.date_cible).days,
        })

    # ---------------------------
    # Alert: En attente depuis > X jours
    # ---------------------------
    alert_param = request.GET.get("alert_days", "3")
    try:
        alert_days = int(alert_param)
    except ValueError:
        alert_days = 3
    if alert_days < 1 or alert_days > 60:
        alert_days = 3

    threshold_date = today - timedelta(days=alert_days)

    overdue_qs = (
        Expedition.objects
        .filter(statut=Expedition.Statut.EN_ATTENTE, date_creation__date__lte=threshold_date)
        .order_by("date_creation")
    )

    overdue_count = overdue_qs.count()

    overdue_list = []
    for e in overdue_qs[:5]:
        overdue_list.append({
            "pk": e.pk,
            "reference": e.reference,
            "client_nom": e.client_nom,
            "origine": e.origine,
            "destination": e.destination,
            "days_waiting": (today - e.date_creation.date()).days,
        })

    # ---------------------------
    # KPIs (global)
    # ---------------------------
    total = Expedition.objects.count()

    by_statut_qs = (
        Expedition.objects.values("statut")
        .annotate(n=Count("id"))
        .order_by("statut")
    )
    statut_map = {row["statut"]: row["n"] for row in by_statut_qs}

    # Données graphique statuts
    statut_labels = [label for _, label in Expedition.Statut.choices]
    statut_keys = [key for key, _ in Expedition.Statut.choices]
    statut_values = [statut_map.get(k, 0) for k in statut_keys]

    # ---------------------------
    # Courbe: créations par jour (période)
    # ---------------------------
    per_day_qs = (
        Expedition.objects.filter(date_creation__date__gte=start, date_creation__date__lte=today)
        .annotate(day=TruncDate("date_creation"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )

    per_day_map = {row["day"]: row["n"] for row in per_day_qs}

    day_list = [start + timedelta(days=i) for i in range(days_selected)]
    per_day_labels = [d.isoformat() for d in day_list]
    per_day_values = [per_day_map.get(d, 0) for d in day_list]

    # ---------------------------
    # Tableaux: dernières expéditions & top destinations
    # ---------------------------
    latest_expeditions = Expedition.objects.order_by("-date_creation")[:5]

    top_destinations = (
        Expedition.objects.values("destination")
        .annotate(n=Count("id"))
        .order_by("-n")[:5]
    )

    context = {
        "days_selected": days_selected,

        "total": total,
        "kpis": {
            "en_attente": statut_map.get(Expedition.Statut.EN_ATTENTE, 0),
            "en_cours": statut_map.get(Expedition.Statut.EN_COURS, 0),
            "livree": statut_map.get(Expedition.Statut.LIVREE, 0),
            "annulee": statut_map.get(Expedition.Statut.ANNULEE, 0),
        },

        "statut_labels_json": json.dumps(statut_labels),
        "statut_values_json": json.dumps(statut_values),

        "per_day_labels_json": json.dumps(per_day_labels),
        "per_day_values_json": json.dumps(per_day_values),

        "latest_expeditions": latest_expeditions,
        "top_destinations": top_destinations,
        "alert_days": alert_days,
        "overdue_count": overdue_count,
        "overdue_list": overdue_list,
        "sla_overdue_count": sla_overdue_count,
        "sla_overdue_list": sla_overdue_list,
    }
    return render(request, "transport/dashboard.html", context)

@staff_member_required
def planifier_livraison(request, pk):
    expedition = get_object_or_404(Expedition, pk=pk)

    if request.method == "POST":
        form = PlanifierLivraisonForm(request.POST)
        if form.is_valid():
            livraison = form.save(commit=False)
            livraison.expedition = expedition
            livraison.statut = Livraison.Statut.PLANIFIEE
            livraison.save()

            # véhicule -> en mission
            vehicule = livraison.vehicule
            vehicule.statut = Vehicule.Statut.EN_MISSION
            vehicule.save(update_fields=["statut"])

            # expédition -> en cours
            expedition.statut = Expedition.Statut.EN_COURS
            expedition.save(update_fields=["statut"])

            # tracking auto
            TrackingEvent.objects.create(
                expedition=expedition,
                statut=Expedition.Statut.EN_COURS,
                commentaire=f"Livraison planifiée avec véhicule {vehicule.immatriculation}",
            )

            return redirect("expedition_detail", pk=expedition.pk)
    else:
        form = PlanifierLivraisonForm()

    return render(request, "transport/planifier_livraison.html", {"expedition": expedition, "form": form})

CLIENT_PAGE_SIZE = 10


@login_required
def client_commandes(request):
    qs = (
        Expedition.objects
        .filter(client_user=request.user)
        .select_related("livraison__vehicule")
        .order_by("-date_creation")
    )
    page_obj = Paginator(qs, CLIENT_PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "transport/client/commandes_list.html",
        {"expeditions": page_obj, "page_obj": page_obj, "is_paginated": page_obj.has_other_pages()},
    )


@login_required
def client_commande_create(request):
    if request.method == "POST":
        form = ClientCommandeCreateForm(request.POST)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.client_user = request.user
            exp.statut = Expedition.Statut.EN_ATTENTE
            exp.save()

            TrackingEvent.objects.create(
                expedition=exp,
                statut=Expedition.Statut.EN_ATTENTE,
                commentaire="Commande créée par le client."
            )

            return render(request, "transport/client/commande_success.html", {"expedition": exp})
    else:
        # Pré-remplir nom/email depuis user si dispo
        initial = {}
        if request.user.first_name or request.user.last_name:
            initial["client_nom"] = f"{request.user.first_name} {request.user.last_name}".strip()
        if request.user.email:
            initial["client_email"] = request.user.email

        form = ClientCommandeCreateForm(initial=initial)

    return render(request, "transport/client/commande_form.html", {"form": form})


@login_required
def client_commande_detail(request, reference):
    exp = get_object_or_404(
        Expedition.objects.select_related("livraison__vehicule"),
        reference=reference,
        client_user=request.user,
    )
    events = exp.events.all()
    return render(request, "transport/client/commande_detail.html", {"expedition": exp, "events": events})


def _restrict_to_instructions(form):
    """Désactive tous les champs sauf 'instructions' (utilisé quand EN_COURS)."""
    allowed = {"instructions"}
    for name, field in form.fields.items():
        if name not in allowed:
            field.disabled = True


@login_required
def client_commande_update(request, reference):
    exp = get_object_or_404(Expedition, reference=reference, client_user=request.user)

    if exp.statut not in (Expedition.Statut.EN_ATTENTE, Expedition.Statut.EN_COURS):
        return HttpResponseForbidden("Commande non modifiable à ce stade.")

    if request.method == "POST":
        form = ClientCommandeUpdateForm(request.POST, instance=exp)
    else:
        form = ClientCommandeUpdateForm(instance=exp)

    if exp.statut == Expedition.Statut.EN_COURS:
        _restrict_to_instructions(form)

    if request.method == "POST" and form.is_valid():
        updated = form.save()
        TrackingEvent.objects.create(
            expedition=updated,
            statut=updated.statut,
            commentaire="Commande modifiée par le client.",
        )
        return redirect("client_commande_detail", reference=updated.reference)

    return render(request, "transport/client/commande_form.html", {"form": form, "expedition": exp})


@login_required
def client_commande_cancel(request, reference):
    exp = get_object_or_404(Expedition, reference=reference, client_user=request.user)

    if exp.statut != Expedition.Statut.EN_ATTENTE:
        return HttpResponseForbidden("Annulation possible uniquement si la commande est en attente.")

    if request.method == "POST":
        raison = request.POST.get("raison_annulation", "").strip()
        exp.statut = Expedition.Statut.ANNULEE
        exp.raison_annulation = raison
        exp.save(update_fields=["statut", "raison_annulation"])

        TrackingEvent.objects.create(
            expedition=exp,
            statut=Expedition.Statut.ANNULEE,
            commentaire=f"Annulée par le client. {raison}".strip()
        )
        return redirect("client_commandes")

    return render(request, "transport/client/commande_cancel.html", {"expedition": exp})

@require_POST
@staff_member_required
def livraison_start(request, pk):
    expedition = get_object_or_404(Expedition, pk=pk)
    if not hasattr(expedition, "livraison"):
        messages.error(request, "Cette expédition n'a pas de livraison planifiée.")
        return redirect("expedition_detail", pk=pk)

    liv = expedition.livraison
    if liv.statut == Livraison.Statut.TERMINEE:
        messages.warning(request, "Livraison déjà terminée.")
        return redirect("expedition_detail", pk=pk)

    liv.statut = Livraison.Statut.EN_COURS
    if not liv.date_depart:
        liv.date_depart = timezone.now()
    liv.save(update_fields=["statut", "date_depart", "position_maj"])

    expedition.statut = Expedition.Statut.EN_COURS
    expedition.save(update_fields=["statut"])

    TrackingEvent.objects.create(
        expedition=expedition,
        statut=Expedition.Statut.EN_COURS,
        commentaire="Livraison démarrée."
    )
    messages.success(request, "Livraison démarrée.")
    return redirect("expedition_detail", pk=pk)


@require_POST
@staff_member_required
def livraison_finish(request, pk):
    expedition = get_object_or_404(Expedition, pk=pk)
    if not hasattr(expedition, "livraison"):
        messages.error(request, "Cette expédition n'a pas de livraison planifiée.")
        return redirect("expedition_detail", pk=pk)

    liv = expedition.livraison
    liv.statut = Livraison.Statut.TERMINEE
    if not liv.date_arrivee:
        liv.date_arrivee = timezone.now()
    liv.save(update_fields=["statut", "date_arrivee", "position_maj"])

    expedition.statut = Expedition.Statut.LIVREE
    expedition.save(update_fields=["statut"])

    TrackingEvent.objects.create(
        expedition=expedition,
        statut=Expedition.Statut.LIVREE,
        commentaire="Livraison terminée."
    )
    messages.success(request, "Livraison terminée.")
    return redirect("expedition_detail", pk=pk)


@login_required
def client_historique(request):
    qs = (
        Expedition.objects
        .filter(
            client_user=request.user,
            statut__in=[Expedition.Statut.LIVREE, Expedition.Statut.ANNULEE],
        )
        .order_by("-date_maj")
    )
    page_obj = Paginator(qs, CLIENT_PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "transport/client/historique.html",
        {"expeditions": page_obj, "page_obj": page_obj, "is_paginated": page_obj.has_other_pages()},
    )


@require_POST
@staff_member_required
def livraison_set_position_demo(request, pk):
    expedition = get_object_or_404(Expedition, pk=pk)

    if not hasattr(expedition, "livraison"):
        return redirect("planifier_livraison", pk=pk)

    liv = expedition.livraison

    # Point demo : Tour Eiffel
    liv.lat = 48.858370
    liv.lng = 2.294481
    liv.position_maj = timezone.now()
    liv.save(update_fields=["lat", "lng", "position_maj"])

    TrackingEvent.objects.create(
        expedition=expedition,
        statut=expedition.statut,
        commentaire="Position GPS mise à jour (demo)."
    )

    return redirect("expedition_detail", pk=pk)