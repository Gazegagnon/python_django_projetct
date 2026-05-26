from django import forms
from django.utils import timezone

from .models import Expedition


class ClientCommandeCreateForm(forms.ModelForm):
    class Meta:
        model = Expedition
        fields = [
            "client_nom",
            "client_email",
            "pickup_adresse",
            "dropoff_adresse",
            "origine",
            "destination",
            "type_colis",
            "poids_kg",
            "instructions",
            "planifiee_pour",
        ]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 3}),
            "planifiee_pour": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_poids_kg(self):
        value = self.cleaned_data.get("poids_kg")
        if value is not None and value <= 0:
            raise forms.ValidationError("Le poids doit être strictement positif.")
        return value

    def clean_planifiee_pour(self):
        value = self.cleaned_data.get("planifiee_pour")
        if value and value < timezone.now():
            raise forms.ValidationError(
                "La date de planification doit être dans le futur."
            )
        return value


class ClientCommandeUpdateForm(forms.ModelForm):
    """
    Modification client : autorisée si EN_ATTENTE.
    Si EN_COURS : uniquement instructions (option pro).
    """
    class Meta:
        model = Expedition
        fields = [
            "pickup_adresse",
            "dropoff_adresse",
            "origine",
            "destination",
            "type_colis",
            "poids_kg",
            "instructions",
            "planifiee_pour",
        ]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 3}),
            "planifiee_pour": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_poids_kg(self):
        value = self.cleaned_data.get("poids_kg")
        if value is not None and value <= 0:
            raise forms.ValidationError("Le poids doit être strictement positif.")
        return value