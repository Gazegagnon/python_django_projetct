from django import forms
from django.utils import timezone

from .models import Livraison, Vehicule


class PlanifierLivraisonForm(forms.ModelForm):
    class Meta:
        model = Livraison
        fields = ["vehicule", "date_depart"]
        widgets = {"date_depart": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicule"].queryset = Vehicule.objects.filter(
            statut=Vehicule.Statut.DISPONIBLE
        )
        self.fields["vehicule"].empty_label = "— Sélectionner un véhicule —"

    def clean_date_depart(self):
        value = self.cleaned_data.get("date_depart")
        if value and value < timezone.now():
            raise forms.ValidationError("La date de départ doit être dans le futur.")
        return value