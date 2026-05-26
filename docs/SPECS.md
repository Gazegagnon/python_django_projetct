# Spécifications des pages — Transport Console

Document de spécification fonctionnelle de chaque page de l'application.

## Conventions

- **Rôle requis** : `visiteur` (anonyme), `client` (utilisateur connecté non
  staff) ou `staff` (`user.is_staff = True`).
- **Méthodes** : verbes HTTP acceptés par la vue.
- **Réponses** : code HTTP retourné par la vue selon la situation.

---

## Index des pages

| # | URL | Vue | Rôle | Template |
|---|---|---|---|---|
| 1 | `/` | `home` | visiteur | `transport/home.html` |
| 2 | `/accounts/login/` | `LoginView` (Django) | visiteur | `registration/login.html` |
| 3 | `/accounts/logout/` | `LogoutView` (Django) | utilisateur | `registration/logged_out.html` |
| 4 | `/suivi/` | `suivi_expedition` | visiteur | `transport/suivi.html` |
| 5 | `/dashboard/` | `dashboard` | staff | `transport/dashboard.html` |
| 6 | `/expeditions/` | `ExpeditionListView` | staff | `transport/expedition_list.html` |
| 7 | `/expeditions/nouvelle/` | `ExpeditionCreateView` | staff | `transport/expedition_form.html` |
| 8 | `/expeditions/<pk>/` | `ExpeditionDetailView` | staff | `transport/expedition_detail.html` |
| 9 | `/expeditions/<pk>/modifier/` | `ExpeditionUpdateView` | staff | `transport/expedition_form.html` |
| 10 | `/expeditions/<pk>/supprimer/` | `ExpeditionDeleteView` | staff | `transport/expedition_confirm_delete.html` |
| 11 | `/expeditions/<pk>/planifier-livraison/` | `planifier_livraison` | staff | `transport/planifier_livraison.html` |
| 12 | `/expeditions/<pk>/livraison/demarrer/` | `livraison_start` | staff | _(redirect)_ |
| 13 | `/expeditions/<pk>/livraison/terminer/` | `livraison_finish` | staff | _(redirect)_ |
| 14 | `/expeditions/<pk>/livraison/demo-position/` | `livraison_set_position_demo` | staff | _(redirect)_ |
| 15 | `/client/commandes/` | `client_commandes` | client | `transport/client/commandes_list.html` |
| 16 | `/client/commandes/nouvelle/` | `client_commande_create` | client | `transport/client/commande_form.html` |
| 17 | `/client/commandes/<ref>/` | `client_commande_detail` | client | `transport/client/commande_detail.html` |
| 18 | `/client/commandes/<ref>/modifier/` | `client_commande_update` | client | `transport/client/commande_form.html` |
| 19 | `/client/commandes/<ref>/annuler/` | `client_commande_cancel` | client | `transport/client/commande_cancel.html` |
| 20 | `/client/historique/` | `client_historique` | client | `transport/client/historique.html` |
| 21 | `/api/expeditions/<ref>/position/` | `expedition_position` | staff ou propriétaire | _(JSON)_ |
| 22 | `/admin/` | Django admin | staff | _(Django)_ |

---

## 1. Accueil — `/`

- **Rôle requis** : aucun (page publique)
- **Méthodes** : GET
- **Contenu** :
  - Hero avec titre, accroche et CTA contextuels (selon état de connexion)
  - Grille de 6 cartes décrivant les fonctionnalités principales
  - Bandeau d'invitation à la connexion (si visiteur)
- **CTA** :
  - Visiteur : « Se connecter » + « Suivre une expédition »
  - Client : « Nouvelle commande » + « Mes commandes »
  - Staff : « Ouvrir le dashboard » + « Voir les expéditions »

## 2. Connexion — `/accounts/login/`

- **Rôle requis** : aucun
- **Méthodes** : GET, POST
- **Form** : `username` + `password` (`AuthenticationForm` Django)
- **Réponses** :
  - GET → 200 affichage du formulaire
  - POST + identifiants valides → 302 vers `next` ou `/client/commandes/`
    (`LOGIN_REDIRECT_URL`)
  - POST + identifiants invalides → 200 avec alerte `Identifiants incorrects`
- **Affichage spécial** : si `?next=...` présent, affiche un message
  informatif « Connexion requise pour accéder à cette page ».

## 3. Déconnexion — `/accounts/logout/`

- **Rôle requis** : utilisateur connecté
- **Méthodes** : **POST uniquement** (via le bouton de la navbar avec CSRF)
- **Réponse** : 302 vers `LOGOUT_REDIRECT_URL = /`, puis affichage de la
  page `logged_out.html`

## 4. Suivi public — `/suivi/`

- **Rôle requis** : aucun
- **Méthodes** : GET
- **Paramètres** : `?reference=EXP-2026-0001`
- **Contenu** :
  - Formulaire de recherche par référence
  - Carte « Expédition » (statut, origine, destination, dates)
  - Carte « Historique » (timeline des `TrackingEvent`)
- **Réponses** :
  - GET sans `reference` → 200 form vide
  - GET avec `reference` valide → 200 + cartes
  - GET avec `reference` inconnue → 200 + alerte `Aucune expédition trouvée`
    (la vue `get_object_or_404` retourne 404 si la référence est inconnue —
    il faut donc en pratique gérer cette différence ; la page affiche une
    alerte si `expedition` n'est pas renseigné mais que `reference` l'est).

## 5. Dashboard — `/dashboard/`

- **Rôle requis** : staff (`@staff_member_required`)
- **Méthodes** : GET
- **Paramètres** :
  - `?days=7|30|90` (période d'analyse, défaut 30)
  - `?alert_days=1|3|7|14|30` (seuil d'alerte attente, défaut 3)
- **Contenu** :
  - Sélecteur de période
  - Cartes d'alerte (SLA dépassé, attente trop longue) si non vides
  - 5 cartes KPI (Total, En attente, En cours, Livrées, Annulées)
  - Doughnut chart « Répartition par statut »
  - Line chart « Créations par jour » sur la période
  - Tableau « 5 dernières expéditions »
  - Tableau « Top destinations »
- **Sécurité** : redirection vers `/admin/login/` si non staff

## 6. Liste des expéditions — `/expeditions/`

- **Rôle requis** : staff
- **Méthodes** : GET
- **Paramètres** :
  - `?q=...` recherche par référence (icontains)
  - `?statut=EN_ATTENTE|EN_COURS|LIVREE|ANNULEE`
  - `?page=N` pagination (10 par page)
- **Contenu** :
  - Header avec total et bouton « Nouvelle expédition »
  - Carte de filtres (recherche + statut)
  - Tableau zébré (Réf, Statut, Client, Origine, Destination, Poids,
    Date cible, Actions)
  - Pagination conservant les filtres via querystring
- **Empty state** : invitation à créer la première expédition

## 7. Création d'expédition — `/expeditions/nouvelle/`

- **Rôle requis** : staff
- **Méthodes** : GET, POST
- **Form** : `ExpeditionForm` (sans `statut` — piloté par le workflow)
- **Sections** : Client / Trajet / Détails
- **Réponses** :
  - POST valide → 302 vers `/expeditions/`
  - POST invalide → 200 avec erreurs inline

## 8. Détail d'une expédition — `/expeditions/<pk>/`

- **Rôle requis** : staff
- **Méthodes** : GET
- **Contenu** :
  - Header avec référence + badge statut coloré
  - Carte « Informations » (client, trajet, type colis, poids, dates,
    description, raison annulation si applicable)
  - Carte « Livraison » :
    - Si livraison : véhicule, statut, dates, position GPS + actions
      `▶️ Démarrer`, `✅ Terminer`, `📍 Position demo` (formulaires POST)
    - Sinon : empty state + bouton « 🚚 Planifier une livraison »
  - Section « 🕓 Historique » (timeline TrackingEvent)
  - Actions globales : retour, modifier, supprimer

## 9. Modification d'une expédition — `/expeditions/<pk>/modifier/`

Identique à la page 7 mais en mode édition. Le titre, le breadcrumb et le
bouton « Annuler » pointent vers la fiche de l'expédition existante.

## 10. Suppression d'une expédition — `/expeditions/<pk>/supprimer/`

- **Rôle requis** : staff
- **Méthodes** : GET (page de confirmation), POST (suppression)
- **Affichage** : carte rouge avec récap + avertissement irréversible
- **Réponse POST** : 302 vers `/expeditions/`

## 11. Planification d'une livraison — `/expeditions/<pk>/planifier-livraison/`

- **Rôle requis** : staff
- **Méthodes** : GET, POST
- **Form** : `PlanifierLivraisonForm` (véhicule disponible, date de départ
  future)
- **Effets de bord (POST valide)** :
  - Création d'un `Livraison` lié à l'expédition (statut `PLANIFIEE`)
  - Statut du véhicule → `EN_MISSION`
  - Statut de l'expédition → `EN_COURS`
  - Création d'un `TrackingEvent` `EN_COURS` (déclenche une notification)
  - Redirection vers `/expeditions/<pk>/`

## 12. Démarrer la livraison — `/expeditions/<pk>/livraison/demarrer/`

- **Rôle requis** : staff
- **Méthodes** : **POST uniquement** (`@require_POST` + CSRF)
- **Réponses** : 302 vers la fiche expédition + message flash
- **Erreurs** :
  - `405` si appel en GET
  - Message flash `error` si pas de livraison planifiée
  - Message flash `warning` si livraison déjà terminée

## 13. Terminer la livraison — `/expeditions/<pk>/livraison/terminer/`

Idem 12. Statut de l'expédition → `LIVREE`, `date_arrivee` posée.

## 14. Position démo — `/expeditions/<pk>/livraison/demo-position/`

- **Rôle requis** : staff
- **Méthodes** : **POST uniquement**
- **Effet** : pose la position GPS sur la Tour Eiffel et crée un événement
  de tracking informatif.

## 15. Mes commandes — `/client/commandes/`

- **Rôle requis** : utilisateur connecté
- **Filtrage** : `Expedition.client_user = request.user`
- **Pagination** : 10 par page
- **Tableau** : Réf, Statut, Origine, Destination, Programmée, Actions
  contextuelles (Voir / Modifier / Annuler / Instructions selon statut)

## 16. Nouvelle commande client — `/client/commandes/nouvelle/`

- **Rôle requis** : utilisateur connecté
- **Méthodes** : GET, POST
- **Form** : `ClientCommandeCreateForm` (nom, email, adresses pickup/dropoff,
  villes, type colis, poids, instructions, planifiée)
- **Pré-remplissage** : `client_nom` et `client_email` depuis le profil user
- **Effets POST valide** :
  - `statut = EN_ATTENTE`
  - `client_user = request.user`
  - Création d'un `TrackingEvent` `EN_ATTENTE`
  - Affichage de `commande_success.html`

## 17. Détail d'une commande client — `/client/commandes/<ref>/`

- **Rôle requis** : utilisateur connecté + propriétaire
- **Contenu** :
  - Carte « Détails » (adresses, type, poids, planification, instructions)
  - Carte « Position du livreur » (Leaflet + polling 5s vers
    `/api/expeditions/<ref>/position/`)
  - Section « 🕓 Historique »
- **Comportement carte** : la carte s'auto-rafraîchit toutes les 5 s ; le
  polling s'arrête quand `statut == LIVREE`.
- **Actions** :
  - Si `EN_ATTENTE` : Modifier / Annuler
  - Si `EN_COURS` : Modifier instructions uniquement
  - Sinon : aucune action

## 18. Modifier une commande client — `/client/commandes/<ref>/modifier/`

- **Règles** :
  - Si `EN_ATTENTE` : tous les champs modifiables
  - Si `EN_COURS` : tous les champs **désactivés** sauf `instructions`
  - Si autre statut : `403 Forbidden`
- Notification email envoyée à chaque modification (via TrackingEvent).

## 19. Annuler une commande — `/client/commandes/<ref>/annuler/`

- **Règles** : possible uniquement si `EN_ATTENTE` (sinon `403`)
- **Form** : champ `raison_annulation` (optionnel)
- **Effets POST** :
  - `statut = ANNULEE`
  - Création d'un `TrackingEvent` `ANNULEE`
  - Redirection vers `/client/commandes/`

## 20. Historique client — `/client/historique/`

- **Rôle requis** : utilisateur connecté
- **Filtrage** : commandes `LIVREE` ou `ANNULEE` du user
- **Pagination** : 10 par page

## 21. API position — `/api/expeditions/<ref>/position/`

- **Rôle requis** : utilisateur connecté (`@login_required`)
- **Autorisation** : `is_staff` ou `client_user_id == request.user.id`
- **Méthodes** : GET
- **Réponses** :
  - `200 application/json` :
    ```json
    {
      "reference": "EXP-2026-0001",
      "has_position": true,
      "lat": 48.85837,
      "lng": 2.294481,
      "updated_at": "2026-05-26T01:24:32+00:00",
      "statut": "EN_COURS"
    }
    ```
  - `200` avec `has_position: false` si pas de livraison ou pas de position
  - `302` vers `/accounts/login/` si anonyme
  - `403 application/json` si utilisateur authentifié mais non autorisé
  - `404` si la référence est inconnue

## 22. Admin Django — `/admin/`

Interface Django standard, accessible aux comptes `is_staff`. Permet
l'édition de tous les modèles, notamment :

- `Expedition` (avec inline `TrackingEvent`)
- `Vehicule`
- `Livraison`
- `TrackingEvent`
- Utilisateurs et groupes

---

## Pages d'erreur

| Code | Template | Quand |
|---|---|---|
| `400` | `400.html` | Requête malformée (CSRF manquant en POST, etc.) |
| `403` | `403.html` | Permission refusée (CSRF invalide, `UserPassesTestMixin` qui refuse) |
| `404` | `404.html` | Page ou objet introuvable |
| `500` | `500.html` | Erreur serveur (template autonome sans context processor) |

> Ces pages ne s'affichent qu'avec `DEBUG=False`. En dev, Django affiche
> ses pages de debug.

## Cycle de vie d'un statut d'expédition

```
EN_ATTENTE ──► EN_COURS ──► LIVREE
     │
     └────► ANNULEE
```

Chaque transition créé un `TrackingEvent` ; un signal `post_save` envoie
alors une notification email au client (via `transport.notifications`).
