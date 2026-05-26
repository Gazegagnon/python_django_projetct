from django import forms

from .models import Vehicule


class VehiculeForm(forms.ModelForm):
    class Meta:
        model = Vehicule
        fields = ["immatriculation", "marque", "modele", "capacite_kg", "statut"]
        widgets = {
            "immatriculation": forms.TextInput(attrs={"placeholder": "Ex : AB-123-CD"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["immatriculation"].required = True
