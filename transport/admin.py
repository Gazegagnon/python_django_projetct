from django.contrib import admin
from .models import Expedition, TrackingEvent


class TrackingInline(admin.TabularInline):
    model = TrackingEvent
    extra = 1


@admin.register(Expedition)
class ExpeditionAdmin(admin.ModelAdmin):
    list_display = ("reference", "statut", "client_nom", "origine", "destination", "date_cible", "poids_kg", "date_creation")
    list_filter = ("statut", "date_creation", "annee", "date_cible",)
    search_fields = ("reference", "client_nom", "client_email", "origine", "destination")
    readonly_fields = ("reference", "annee", "numero", "date_creation", "date_maj")
    inlines = [TrackingInline]


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ("expedition", "statut", "date_event")
    list_filter = ("statut", "date_event")
    search_fields = ("expedition__reference", "commentaire")

from .models import Vehicule, Livraison

@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ("immatriculation", "statut", "capacite_kg", "marque", "modele")
    list_filter = ("statut",)
    search_fields = ("immatriculation", "marque", "modele")

@admin.register(Livraison)
class LivraisonAdmin(admin.ModelAdmin):
    list_display = ("expedition", "vehicule", "statut", "date_depart", "date_arrivee")
    list_filter = ("statut",)
    search_fields = ("expedition__reference", "vehicule__immatriculation")