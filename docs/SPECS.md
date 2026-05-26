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
| 3 | `/accounts/inscription/` | `SignupView` | visiteur | `registration/signup.html` |
| 4 | `/accounts/logout/` | `LogoutView` (Django) | utilisateur | `registration/logged_out.html` |
| 5 | `/accounts/password_reset/` | Django auth | visiteur | `registration/password_reset_form.html` |
| 6 | `/suivi/` | `suivi_expedition` | visiteur | `transport/suivi.html` |
| 7 | `/dashboard/` | `dashboard` | staff | `transport/dashboard.html` |
| 8 | `/expeditions/` | `ExpeditionListView` | staff | `transport/expedition_list.html` |
| 9 | `/expeditions/export/` | `expedition_export_csv` | staff | _(CSV)_ |
| 10 | `/expeditions/nouvelle/` | `ExpeditionCreateView` | staff | `transport/expedition_form.html` |
| 11 | `/expeditions/<pk>/` | `ExpeditionDetailView` | staff | `transport/expedition_detail.html` |
| 12 | `/expeditions/<pk>/modifier/` | `ExpeditionUpdateView` | staff | `transport/expedition_form.html` |
| 13 | `/expeditions/<pk>/supprimer/` | `ExpeditionDeleteView` | staff | `transport/expedition_confirm_delete.html` |
| 14 | `/expeditions/<pk>/planifier-livraison/` | `planifier_livraison` | staff | `transport/planifier_livraison.html` |
| 15 | `/expeditions/<pk>/livraison/demarrer/` | `livraison_start` | staff | _(redirect)_ |
| 16 | `/expeditions/<pk>/livraison/terminer/` | `livraison_finish` | staff | _(redirect)_ |
| 17 | `/expeditions/<pk>/livraison/demo-position/` | `livraison_set_position_demo` | staff | _(redirect)_ |
| 18 | `/client/commandes/` | `client_commandes` | client | `transport/client/commandes_list.html` |
| 19 | `/client/commandes/nouvelle/` | `client_commande_create` | client | `transport/client/commande_form.html` |
| 20 | `/client/commandes/<ref>/` | `client_commande_detail` | client | `transport/client/commande_detail.html` |
| 21 | `/client/commandes/<ref>/modifier/` | `client_commande_update` | client | `transport/client/commande_form.html` |
| 22 | `/client/commandes/<ref>/annuler/` | `client_commande_cancel` | client | `transport/client/commande_cancel.html` |
| 23 | `/client/historique/` | `client_historique` | client | `transport/client/historique.html` |
| 24 | `/api/expeditions/<ref>/position/` | `expedition_position` | staff ou propriétaire | _(JSON)_ |
| 25 | `/admin/` | Django admin | staff | _(Django)_ |

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

## 3. Inscription — `/accounts/inscription/`

- **Rôle requis** : aucun (visiteur)
- **Méthodes** : GET, POST
- **Form** : `SignupForm` (`username`, `email`, `password1`, `password2`)
- **Réponses** :
  - POST valide → création du compte, connexion automatique, 302 vers
    `/client/commandes/`
  - POST invalide → 200 avec erreurs inline
- **Liens** : depuis la page de connexion et la navbar (visiteur)

## 4. Déconnexion — `/accounts/logout/`

- **Rôle requis** : utilisateur connecté
- **Méthodes** : **POST uniquement** (via le bouton de la navbar avec CSRF)
- **Réponse** : 302 vers `LOGOUT_REDIRECT_URL = /`, puis affichage de la
  page `logged_out.html`

## 5. Réinitialisation du mot de passe — `/accounts/password_reset/`

- **Rôle requis** : aucun
- **Méthodes** : GET, POST (+ pages confirm / complete Django auth)
- **Templates** : `password_reset_form.html`, `password_reset_done.html`,
  `password_reset_confirm.html`, `password_reset_complete.html`
- **Lien** : depuis la page de connexion

## 6. Suivi public — `/suivi/`

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
  - GET avec `reference` inconnue → **200** + alerte
    « Aucune expédition trouvée » (pas de 404)

## 7. Dashboard — `/dashboard/`

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

## 8. Liste des expéditions — `/expeditions/`

- **Rôle requis** : staff
- **Méthodes** : GET
- **Paramètres** :
  - `?q=...` recherche multi-champs (référence, client, email, origine,
    destination)
  - `?statut=EN_ATTENTE|EN_COURS|LIVREE|ANNULEE`
  - `?page=N` pagination (10 par page)
- **Contenu** :
  - Header avec total, bouton « Nouvelle expédition » et **Export CSV**
  - Carte de filtres (recherche + statut)
  - Tableau zébré (Réf, Statut, Client, Origine, Destination, Poids,
    Date cible, Actions)
  - Pagination conservant les filtres via querystring
- **Empty state** : invitation à créer la première expédition

## 9. Export CSV — `/expeditions/export/`

- **Rôle requis** : staff (`@staff_member_required`)
- **Méthodes** : GET
- **Paramètres** : mêmes filtres `q` et `statut` que la liste
- **Réponse** : fichier `expeditions.csv` (UTF-8 BOM) avec colonnes
  reference, statut, client_nom, client_email, origine, destination,
  poids_kg, date_cible, date_creation

## 10. Création d'expédition — `/expeditions/nouvelle/`

- **Rôle requis** : staff
- **Méthodes** : GET, POST
- **Form** : `ExpeditionForm` (sans `statut` — piloté par le workflow)
- **Sections** : Client / Trajet / Détails
- **Réponses** :
  - POST valide → 302 vers `/expeditions/`
  - POST invalide → 200 avec erreurs inline

## 11. Détail d'une expédition — `/expeditions/<pk>/`

- **Rôle requis** : staff
- **Méthodes** : GET
- **Contenu** :
  - Header avec référence + badge statut coloré
  - Carte « Informations » (client, trajet, type colis, poids, dates,
    description, raison annulation si applicable)
  - Carte « Livraison » :
    - Si livraison : véhicule, statut, dates, **carte Leaflet staff** (polling
      avec backoff) + actions `▶️ Démarrer`, `✅ Terminer`, `📍 Position demo`
      (formulaires POST avec confirmation JS)
    - Sinon : empty state + bouton « 🚚 Planifier une livraison »
  - Section « 🕓 Historique » (timeline TrackingEvent)
  - Actions globales : retour, modifier, supprimer

## 12. Modification d'une expédition — `/expeditions/<pk>/modifier/`

Identique à la page 7 mais en mode édition. Le titre, le breadcrumb et le
bouton « Annuler » pointent vers la fiche de l'expédition existante.

## 13. Suppression d'une expédition — `/expeditions/<pk>/supprimer/`

- **Rôle requis** : staff
- **Méthodes** : GET (page de confirmation), POST (suppression)
- **Affichage** : carte rouge avec récap + avertissement irréversible
- **Réponse POST** : 302 vers `/expeditions/`

## 14. Planification d'une livraison — `/expeditions/<pk>/planifier-livraison/`

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

## 15. Démarrer la livraison — `/expeditions/<pk>/livraison/demarrer/`

- **Rôle requis** : staff
- **Méthodes** : **POST uniquement** (`@require_POST` + CSRF)
- **Réponses** : 302 vers la fiche expédition + message flash
- **Erreurs** :
  - `405` si appel en GET
  - Message flash `error` si pas de livraison planifiée
  - Message flash `warning` si livraison déjà terminée

## 16. Terminer la livraison — `/expeditions/<pk>/livraison/terminer/`

Idem 15. Statut de l'expédition → `LIVREE`, `date_arrivee` posée, véhicule
remis au statut `DISPONIBLE` (`release_vehicule`).

## 17. Position démo — `/expeditions/<pk>/livraison/demo-position/`

- **Rôle requis** : staff
- **Méthodes** : **POST uniquement**
- **Effet** : pose la position GPS sur la Tour Eiffel et crée un événement
  de tracking informatif.

## 18. Mes commandes — `/client/commandes/`

- **Rôle requis** : utilisateur connecté
- **Filtrage** : `Expedition.client_user = request.user`
- **Pagination** : 10 par page
- **Tableau** : Réf, Statut, Origine, Destination, Programmée, Actions
  contextuelles (Voir / Modifier / Annuler / Instructions selon statut)

## 19. Nouvelle commande client — `/client/commandes/nouvelle/`

- **Rôle requis** : utilisateur connecté
- **Méthodes** : GET, POST
- **Form** : `ClientCommandeCreateForm` (nom, email, adresses pickup/dropoff,
  villes, type colis, poids, instructions, planifiée)
- **Pré-remplissage** : `client_nom` et `client_email` depuis le profil user
- **Effets POST valide** :
  - `statut = EN_ATTENTE`
  - `client_user = request.user`
  - Création d'un `TrackingEvent` `EN_ATTENTE` (sans email — filtré par signal)

## 20. Détail d'une commande client — `/client/commandes/<ref>/`

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

## 21. Modifier une commande client — `/client/commandes/<ref>/modifier/`

- **Règles** :
  - Si `EN_ATTENTE` : tous les champs modifiables
  - Si `EN_COURS` : tous les champs **désactivés** sauf `instructions`
  - Si autre statut : `403 Forbidden`
- Notification email **non** envoyée pour « Commande modifiée par le client. »

## 22. Annuler une commande — `/client/commandes/<ref>/annuler/`

- **Règles** : possible uniquement si `EN_ATTENTE` (sinon `403`)
- **Form** : champ `raison_annulation` (optionnel)
- **Effets POST** :
  - `statut = ANNULEE`
  - Si livraison planifiée : `Livraison.statut = ANNULEE` + véhicule
    `DISPONIBLE`
  - Création d'un `TrackingEvent` `ANNULEE`
  - Redirection vers `/client/commandes/`

## 23. Historique client — `/client/historique/`

- **Rôle requis** : utilisateur connecté
- **Filtrage** : commandes `LIVREE` ou `ANNULEE` du user
- **Pagination** : 10 par page

## 24. API position — `/api/expeditions/<ref>/position/`

- **Rôle requis** : utilisateur connecté (`@login_required`)
- **Autorisation** : `is_staff` ou `client_user_id == request.user.id`
- **Limitation** : 120 requêtes / heure / utilisateur (`@rate_limit`)
- **Méthodes** : GET
- **Réponses** :
  - `200 application/json` :
    ```json
    {
      "reference": "EXP-2026-0001",
      "statut": "EN_COURS",
      "livraison_statut": "EN_COURS",
      "has_position": true,
      "lat": 48.85837,
      "lng": 2.294481,
      "updated_at": "2026-05-26T01:24:32+00:00"
    }
    ```
  - `200` avec `has_position: false` si pas de livraison ou pas de position
  - `302` vers `/accounts/login/` si anonyme
  - `403 application/json` si utilisateur authentifié mais non autorisé
  - `429` si quota de requêtes dépassé
  - `404` si la référence est inconnue

## 25. Admin Django — `/admin/`

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
alors une notification email au client (via `transport.notifications`),
**sauf** pour les événements « Commande créée/modifiée par le client. »
(filtrés par `should_notify_tracking_event`).
