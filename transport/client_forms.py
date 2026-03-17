from django import forms
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