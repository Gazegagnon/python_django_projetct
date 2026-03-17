from django.urls import path

from .views import (
    home,
    dashboard,
    suivi_expedition,
    planifier_livraison,
    expedition_position,

    ExpeditionListView,
    ExpeditionDetailView,
    ExpeditionCreateView,
    ExpeditionUpdateView,
    ExpeditionDeleteView,
    

    client_commandes,
    client_commande_create,
    client_commande_detail,
    client_commande_update,
    client_commande_cancel,
    client_historique,
    livraison_start,
    livraison_finish,
    livraison_set_position_demo,
)

urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("suivi/", suivi_expedition, name="suivi_expedition"),

    path("expeditions/", ExpeditionListView.as_view(), name="expedition_list"),
    path("expeditions/nouvelle/", ExpeditionCreateView.as_view(), name="expedition_create"),
    path("expeditions/<int:pk>/", ExpeditionDetailView.as_view(), name="expedition_detail"),
    path("expeditions/<int:pk>/modifier/", ExpeditionUpdateView.as_view(), name="expedition_update"),
    path("expeditions/<int:pk>/supprimer/", ExpeditionDeleteView.as_view(), name="expedition_delete"),
    path("expeditions/<int:pk>/planifier-livraison/", planifier_livraison, name="planifier_livraison"),

    path("expeditions/<int:pk>/livraison/demarrer/", livraison_start, name="livraison_start"),
    path("expeditions/<int:pk>/livraison/terminer/", livraison_finish, name="livraison_finish"),
    path("expeditions/<int:pk>/livraison/demo-position/", livraison_set_position_demo, name="livraison_demo_position"),

    path("client/commandes/", client_commandes, name="client_commandes"),
    path("client/commandes/nouvelle/", client_commande_create, name="client_commande_create"),
    path("client/commandes/<str:reference>/", client_commande_detail, name="client_commande_detail"),
    path("client/commandes/<str:reference>/modifier/", client_commande_update, name="client_commande_update"),
    path("client/commandes/<str:reference>/annuler/", client_commande_cancel, name="client_commande_cancel"),
    path("client/historique/", client_historique, name="client_historique"),

    path("api/expeditions/<str:reference>/position/", expedition_position, name="expedition_position"),
]