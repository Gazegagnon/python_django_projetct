from django import forms
from .models import Expedition


class ExpeditionForm(forms.ModelForm):
    """Formulaire staff. Le champ ``statut`` n'est pas exposé : le cycle de vie
    est piloté par le workflow (planification → démarrage → fin de livraison).
    Pour une correction exceptionnelle, passer par l'admin Django."""

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