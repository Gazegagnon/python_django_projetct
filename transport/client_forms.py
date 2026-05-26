from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import AvisLivraison, ClientMessage, Expedition


class BaseClientForm(forms.ModelForm):
    """Validations communes aux formulaires client."""

    def clean_poids_kg(self):
        value = self.cleaned_data.get("poids_kg")
        if value is not None and value <= 0:
            raise forms.ValidationError("Le poids doit être strictement positif.")
        return value


class ClientCommandeCreateForm(BaseClientForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("client_nom", "client_email", "origine", "destination", "poids_kg"):
            self.fields[name].required = True

    def clean_planifiee_pour(self):
        value = self.cleaned_data.get("planifiee_pour")
        if value and value < timezone.now():
            raise forms.ValidationError(
                "La date de planification doit être dans le futur."
            )
        return value


class ClientCommandeUpdateForm(BaseClientForm):
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


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ClientMessageForm(forms.ModelForm):
    class Meta:
        model = ClientMessage
        fields = ["sujet", "corps"]
        widgets = {"corps": forms.Textarea(attrs={"rows": 4, "placeholder": "Votre demande ou suggestion…"})}
        labels = {"sujet": "Sujet", "corps": "Message"}


class AvisLivraisonForm(forms.ModelForm):
    class Meta:
        model = AvisLivraison
        fields = ["note", "commentaire"]
        widgets = {
            "note": forms.NumberInput(attrs={"min": 1, "max": 5, "step": 1}),
            "commentaire": forms.Textarea(attrs={"rows": 3, "placeholder": "Comment s'est passée la livraison ?"}),
        }
        labels = {"note": "Note (1 à 5)", "commentaire": "Commentaire"}

    def clean_note(self):
        note = self.cleaned_data.get("note")
        if note is not None and (note < 1 or note > 5):
            raise forms.ValidationError("La note doit être entre 1 et 5.")
        return note
