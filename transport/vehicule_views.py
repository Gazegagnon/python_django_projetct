"""CRUD véhicules pour le staff (hors admin Django)."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .models import Livraison, Vehicule
from .services import release_vehicule
from .vehicule_forms import VehiculeForm
from .views import StaffRequiredMixin


class VehiculeListView(StaffRequiredMixin, ListView):
    model = Vehicule
    template_name = "transport/vehicule_list.html"
    context_object_name = "vehicules"
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset().annotate(nb_livraisons=Count("livraisons"))
        statut = self.request.GET.get("statut", "")
        if statut:
            qs = qs.filter(statut=statut)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(immatriculation__icontains=q)
        return qs.order_by("statut", "immatriculation")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_statut"] = self.request.GET.get("statut", "")
        ctx["current_q"] = self.request.GET.get("q", "")
        ctx["statut_choices"] = Vehicule.Statut.choices
        ctx["counts"] = {
            "total": Vehicule.objects.count(),
            "disponible": Vehicule.objects.filter(statut=Vehicule.Statut.DISPONIBLE).count(),
            "en_mission": Vehicule.objects.filter(statut=Vehicule.Statut.EN_MISSION).count(),
            "maintenance": Vehicule.objects.filter(statut=Vehicule.Statut.MAINTENANCE).count(),
        }
        return ctx


class VehiculeCreateView(StaffRequiredMixin, CreateView):
    model = Vehicule
    form_class = VehiculeForm
    template_name = "transport/vehicule_form.html"
    success_url = reverse_lazy("vehicule_list")

    def form_valid(self, form):
        messages.success(self.request, f"Véhicule {form.instance.immatriculation} créé.")
        return super().form_valid(form)


class VehiculeUpdateView(StaffRequiredMixin, UpdateView):
    model = Vehicule
    form_class = VehiculeForm
    template_name = "transport/vehicule_form.html"
    context_object_name = "vehicule"

    def get_success_url(self):
        messages.success(self.request, "Véhicule mis à jour.")
        return reverse_lazy("vehicule_list")

    def form_valid(self, form):
        if (
            form.instance.statut == Vehicule.Statut.DISPONIBLE
            and form.instance.livraison_active
        ):
            form.add_error(
                "statut",
                "Impossible de passer en Disponible : une livraison active est liée.",
            )
            return self.form_invalid(form)
        return super().form_valid(form)


class VehiculeDeleteView(StaffRequiredMixin, DeleteView):
    model = Vehicule
    template_name = "transport/vehicule_confirm_delete.html"
    success_url = reverse_lazy("vehicule_list")
    context_object_name = "vehicule"

    def form_valid(self, form):
        if self.object.livraisons.exists():
            messages.error(
                self.request,
                "Impossible de supprimer : ce véhicule a des livraisons associées.",
            )
            return redirect("vehicule_update", pk=self.object.pk)
        messages.success(self.request, "Véhicule supprimé.")
        return super().form_valid(form)


@require_POST
@staff_member_required
def vehicule_release(request, pk):
    """Remet un véhicule bloqué EN_MISSION sans livraison active."""
    vehicule = get_object_or_404(Vehicule, pk=pk)
    if vehicule.livraison_active:
        messages.error(request, "Ce véhicule a encore une livraison active.")
    else:
        release_vehicule(vehicule)
        messages.success(request, f"{vehicule.immatriculation} est de nouveau disponible.")
    return redirect("vehicule_list")
