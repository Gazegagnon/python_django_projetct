import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .client_forms import (
    AvisLivraisonForm,
    ClientCommandeCreateForm,
    ClientCommandeUpdateForm,
    ClientMessageForm,
)
from .forms import ExpeditionForm
from .livraison_forms import PlanifierLivraisonForm
from .models import (
    AvisLivraison,
    ClientMessage,
    Expedition,
    Livraison,
    Notification,
    TrackingEvent,
    Vehicule,
)
from .inapp_notifications import notify_expedition_client, notify_staff
from .services import (
    assign_livraison_planifiee,
    cancel_livraison_for_expedition,
    filter_expeditions_queryset,
    get_page,
    pagination_context,
    release_vehicule,
    vehicule_stat_counts,
)
from .throttling import rate_limit


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
        return filter_expeditions_queryset(
            qs,
            q=self.request.GET.get("q", ""),
            statut=self.request.GET.get("statut", ""),
        )

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
        if hasattr(self.object, "livraison"):
            ctx["position_url"] = reverse(
                "expedition_position", args=[self.object.reference]
            )
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
    not_found = False
    reference = (request.GET.get("reference") or "").strip()

    if reference:
        expedition = Expedition.objects.filter(reference=reference).first()
        if expedition:
            events = expedition.events.all()
        else:
            not_found = True

    return render(
        request,
        "transport/suivi.html",
        {
            "expedition": expedition,
            "events": events,
            "reference": reference,
            "not_found": not_found,
        },
    )


@login_required
@rate_limit(limit=120, window=3600)
def expedition_position(request, reference):
    exp = get_object_or_404(
        Expedition.objects.select_related("livraison"),
        reference=reference,
    )

    is_staff = request.user.is_staff
    is_owner = exp.client_user_id is not None and exp.client_user_id == request.user.id
    if not (is_staff or is_owner):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    liv = getattr(exp, "livraison", None)
    payload = {
        "reference": exp.reference,
        "statut": exp.statut,
        "livraison_statut": liv.statut if liv else None,
        "has_position": False,
        "lat": None,
        "lng": None,
        "updated_at": None,
    }

    if liv and liv.lat is not None and liv.lng is not None:
        payload.update(
            {
                "has_position": True,
                "lat": float(liv.lat),
                "lng": float(liv.lng),
                "updated_at": liv.position_maj.isoformat() if liv.position_maj else None,
            }
        )

    return JsonResponse(payload)


@staff_member_required
def dashboard(request):
    """Redirige vers la vue d'ensemble (dashboard scindé)."""
    return redirect("dashboard_overview")

@staff_member_required
def planifier_livraison(request, pk):
    expedition = get_object_or_404(
        Expedition.objects.select_related("livraison__vehicule"),
        pk=pk,
    )
    existing = getattr(expedition, "livraison", None)

    if expedition.statut in (Expedition.Statut.LIVREE, Expedition.Statut.ANNULEE):
        messages.error(request, "Impossible de planifier une livraison pour cette expédition.")
        return redirect("expedition_detail", pk=pk)

    if existing and existing.statut in (
        Livraison.Statut.PLANIFIEE,
        Livraison.Statut.EN_COURS,
    ):
        messages.warning(request, "Une livraison est déjà active pour cette expédition.")
        return redirect("expedition_detail", pk=pk)

    if request.method == "POST":
        form = PlanifierLivraisonForm(request.POST)
        if form.is_valid():
            vehicule = form.cleaned_data["vehicule"]
            date_depart = form.cleaned_data.get("date_depart")
            try:
                livraison = assign_livraison_planifiee(
                    expedition=expedition,
                    vehicule=vehicule,
                    date_depart=date_depart,
                    existing=existing,
                )
            except ValueError:
                messages.warning(request, "Une livraison est déjà active pour cette expédition.")
                return redirect("expedition_detail", pk=pk)

            TrackingEvent.objects.create(
                expedition=expedition,
                statut=Expedition.Statut.EN_COURS,
                commentaire=f"Livraison planifiée avec véhicule {livraison.vehicule.immatriculation}",
            )
            notify_expedition_client(
                expedition=expedition,
                categorie=Notification.Categorie.LIVRAISON_PLANIFIEE,
                titre=f"Livraison planifiée — {expedition.reference}",
                message=f"Véhicule {livraison.vehicule.immatriculation} assigné. Départ prévu prochainement.",
            )
            messages.success(request, "Livraison planifiée.")
            return redirect("expedition_detail", pk=expedition.pk)
    else:
        form = PlanifierLivraisonForm()

    counts = vehicule_stat_counts()
    return render(
        request,
        "transport/planifier_livraison.html",
        {
            "expedition": expedition,
            "form": form,
            "vehicule_counts": counts,
            "replannification": bool(
                existing
                and existing.statut
                in (Livraison.Statut.ANNULEE, Livraison.Statut.TERMINEE)
            ),
        },
    )

CLIENT_PAGE_SIZE = 10


@login_required
def client_commandes(request):
    qs = (
        Expedition.objects.filter(client_user=request.user)
        .select_related("livraison__vehicule")
        .order_by("-date_creation")
    )
    page_obj = get_page(request, qs, per_page=CLIENT_PAGE_SIZE)
    ctx = pagination_context(page_obj)
    ctx["expeditions"] = page_obj
    return render(request, "transport/client/commandes_list.html", ctx)


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
            notify_staff(
                categorie=Notification.Categorie.EN_ATTENTE,
                titre=f"Nouvelle commande {exp.reference}",
                message=f"{exp.client_nom} — {exp.origine} → {exp.destination}. En attente d'assignation.",
                lien=reverse("expedition_detail", args=[exp.pk]),
                expedition=exp,
            )
            notify_expedition_client(
                expedition=exp,
                categorie=Notification.Categorie.CONFIRMATION,
                titre="Commande enregistrée",
                message="Votre commande est en attente de planification par notre équipe.",
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
    return render(
        request,
        "transport/client/commande_detail.html",
        {
            "expedition": exp,
            "events": events,
            "position_url": reverse("expedition_position", args=[exp.reference]),
            "message_form": ClientMessageForm(),
            "avis_form": AvisLivraisonForm(),
            "has_avis": hasattr(exp, "avis"),
            "client_messages": exp.messages_client.all()[:5],
        },
    )


def _restrict_to_instructions(form):
    """Désactive tous les champs sauf 'instructions' (utilisé quand EN_COURS)."""
    allowed = {"instructions"}
    for name, field in form.fields.items():
        if name not in allowed:
            field.disabled = True


@login_required
def client_commande_update(request, reference):
    exp = get_object_or_404(
        Expedition.objects.select_related("livraison__vehicule"),
        reference=reference,
        client_user=request.user,
    )

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
    exp = get_object_or_404(
        Expedition.objects.select_related("livraison__vehicule"),
        reference=reference,
        client_user=request.user,
    )

    if exp.statut != Expedition.Statut.EN_ATTENTE:
        return HttpResponseForbidden("Annulation possible uniquement si la commande est en attente.")

    if request.method == "POST":
        raison = request.POST.get("raison_annulation", "").strip()
        exp.statut = Expedition.Statut.ANNULEE
        exp.raison_annulation = raison
        exp.save(update_fields=["statut", "raison_annulation"])
        cancel_livraison_for_expedition(exp)

        TrackingEvent.objects.create(
            expedition=exp,
            statut=Expedition.Statut.ANNULEE,
            commentaire=f"Annulée par le client. {raison}".strip()
        )
        notify_staff(
            categorie=Notification.Categorie.ANNULEE,
            titre=f"Commande annulée — {exp.reference}",
            message=f"Annulée par le client. Raison : {raison or 'non précisée'}.",
            lien=reverse("expedition_detail", args=[exp.pk]),
            expedition=exp,
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
    notify_expedition_client(
        expedition=expedition,
        categorie=Notification.Categorie.EN_COURS,
        titre=f"Livraison en cours — {expedition.reference}",
        message="Votre colis est en route. Suivez la position sur votre espace client.",
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

    release_vehicule(liv.vehicule)

    expedition.statut = Expedition.Statut.LIVREE
    expedition.save(update_fields=["statut"])

    TrackingEvent.objects.create(
        expedition=expedition,
        statut=Expedition.Statut.LIVREE,
        commentaire="Livraison terminée."
    )
    notify_expedition_client(
        expedition=expedition,
        categorie=Notification.Categorie.LIVREE,
        titre=f"Livraison effectuée — {expedition.reference}",
        message="Votre commande a été livrée. Vous pouvez laisser un avis sur la page de détail.",
    )
    messages.success(request, "Livraison terminée.")
    return redirect("expedition_detail", pk=pk)


@login_required
def client_historique(request):
    qs = (
        Expedition.objects.filter(
            client_user=request.user,
            statut__in=[Expedition.Statut.LIVREE, Expedition.Statut.ANNULEE],
        )
        .order_by("-date_maj")
    )
    page_obj = get_page(request, qs, per_page=CLIENT_PAGE_SIZE)
    ctx = pagination_context(page_obj)
    ctx["expeditions"] = page_obj
    return render(request, "transport/client/historique.html", ctx)


@staff_member_required
def expedition_export_csv(request):
    """Export CSV des expéditions (respecte les filtres GET de la liste)."""
    qs = filter_expeditions_queryset(
        Expedition.objects.select_related("client_user").order_by("-date_creation"),
        q=request.GET.get("q", ""),
        statut=request.GET.get("statut", ""),
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="expeditions.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(
        [
            "reference",
            "statut",
            "client_nom",
            "client_email",
            "origine",
            "destination",
            "poids_kg",
            "date_cible",
            "date_creation",
        ]
    )
    for exp in qs:
        writer.writerow(
            [
                exp.reference,
                exp.get_statut_display(),
                exp.client_nom,
                exp.client_email,
                exp.origine,
                exp.destination,
                exp.poids_kg or "",
                exp.date_cible or "",
                exp.date_creation.isoformat(),
            ]
        )
    return response


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


@require_POST
@login_required
def client_commande_message(request, reference):
    exp = get_object_or_404(
        Expedition,
        reference=reference,
        client_user=request.user,
    )
    form = ClientMessageForm(request.POST)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.expedition = exp
        msg.auteur = request.user
        msg.save()
        notify_staff(
            categorie=Notification.Categorie.MESSAGE_CLIENT,
            titre=f"Message client — {exp.reference}",
            message=f"{msg.sujet} : {msg.corps[:200]}",
            lien=reverse("expedition_detail", args=[exp.pk]),
            expedition=exp,
        )
        messages.success(request, "Votre message a été envoyé à l'équipe.")
    else:
        messages.error(request, "Message invalide.")
    return redirect("client_commande_detail", reference=reference)


@require_POST
@login_required
def client_commande_avis(request, reference):
    exp = get_object_or_404(
        Expedition,
        reference=reference,
        client_user=request.user,
    )
    if exp.statut != Expedition.Statut.LIVREE:
        return HttpResponseForbidden("Avis possible uniquement après livraison.")
    if hasattr(exp, "avis"):
        messages.warning(request, "Vous avez déjà laissé un avis pour cette commande.")
        return redirect("client_commande_detail", reference=reference)

    form = AvisLivraisonForm(request.POST)
    if form.is_valid():
        avis = form.save(commit=False)
        avis.expedition = exp
        avis.auteur = request.user
        avis.save()
        notify_staff(
            categorie=Notification.Categorie.AVIS_CLIENT,
            titre=f"Avis {avis.note}/5 — {exp.reference}",
            message=avis.commentaire or "Sans commentaire.",
            lien=reverse("expedition_detail", args=[exp.pk]),
            expedition=exp,
        )
        messages.success(request, "Merci pour votre avis !")
    else:
        messages.error(request, "Avis invalide.")
    return redirect("client_commande_detail", reference=reference)