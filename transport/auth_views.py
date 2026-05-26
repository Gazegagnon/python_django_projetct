"""Vues d'authentification (inscription)."""

from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .client_forms import SignupForm


class SignupView(CreateView):
    form_class = SignupForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("client_commandes")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
