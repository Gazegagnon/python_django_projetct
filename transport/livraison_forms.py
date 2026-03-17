from django import forms
from .models import Livraison, Vehicule

class PlanifierLivraisonForm(forms.ModelForm):
    class Meta:
        model = Livraison
        fields = ["vehicule", "date_depart"]
        widgets = {"date_depart": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicule"].queryset = Vehicule.objects.filter(statut=Vehicule.Statut.DISPONIBLE)