from django import forms

from .models import Expedition


class ExpeditionForm(forms.ModelForm):
    """Formulaire staff. Le statut est piloté par le workflow livraison."""

    class Meta:
        model = Expedition
        fields = [
            "client_nom",
            "client_email",
            "origine",
            "destination",
            "poids_kg",
            "description",
            "date_cible",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "date_cible": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("client_nom", "client_email", "origine", "destination"):
            self.fields[name].required = True
