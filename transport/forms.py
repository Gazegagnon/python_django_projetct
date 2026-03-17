from django import forms
from .models import Expedition

class ExpeditionForm(forms.ModelForm):
    class Meta:
        model = Expedition
        fields = [
            "client_nom",
            "client_email",
            "origine",
            "destination",
            "poids_kg",
            "description",
            "statut",
            "date_cible",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "date_cible": forms.DateInput(attrs={"type": "date"}),
        }