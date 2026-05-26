# Transport Console

Application Django de gestion d'expéditions, de livraisons et de suivi GPS en
temps réel. Trois rôles cloisonnés : **visiteur**, **client connecté** et
**staff opérationnel**.

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Installation](#installation)
- [Lancement](#lancement)
- [Comptes de démo](#comptes-de-démo)
- [Variables d'environnement](#variables-denvironnement)
- [Tests](#tests)
- [Structure du projet](#structure-du-projet)
- [Spécifications des pages](#spécifications-des-pages)
- [Workflow d'une expédition](#workflow-dune-expédition)
- [Sécurité](#sécurité)

---

## Fonctionnalités

- 📦 **CRUD d'expéditions** (staff) avec référence auto `EXP-AAAA-NNNN`.
- 👤 **Espace client** : création de commande, suivi, modification, annulation,
  historique.
- 🚚 **Planification de livraisons** avec sélection d'un véhicule disponible.
- 📍 **Suivi GPS temps réel** via carte Leaflet + endpoint JSON.
- 📊 **Dashboard décisionnel** (KPI, doughnut/line charts Chart.js).
- ⚠️ **Alertes SLA** (date cible dépassée, attente prolongée) avec seuils.
- ✉️ **Notifications email** automatiques sur changement de statut (signal
  `post_save` sur `TrackingEvent`).
- 🌓 **Thème clair / sombre** (préférence persistée dans `localStorage`).
- 🔐 **Authentification** Django (login/logout) avec redirections contextuelles.
- 🛡️ **Sécurité** : protection CSRF, actions destructives en POST,
  `LoginRequiredMixin` + `UserPassesTestMixin` sur tout l'admin métier,
  durcissement automatique en production.

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Python ≥ 3.11, Django 6.0 |
| Base de données | SQLite (par défaut), compatible PostgreSQL |
| Front | HTML5, CSS custom (design system maison), Vanilla JS |
| Charts | [Chart.js](https://www.chartjs.org/) (CDN) |
| Cartographie | [Leaflet](https://leafletjs.com/) + OpenStreetMap (CDN) |
| Tests | `django.test.TestCase` (14 tests d'intégration) |

## Installation

```powershell
# 1. Cloner et entrer dans le projet
git clone <url-du-repo> django_project
cd django_project

# 2. Créer puis activer le venv
python -m venv venv
.\venv\Scripts\Activate.ps1   # PowerShell
# source venv/bin/activate    # macOS / Linux

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. (Optionnel) Configurer les variables d'environnement
copy .env.example .env        # éditer ensuite .env

# 5. Appliquer les migrations
python manage.py migrate

# 6. Créer un superuser
python manage.py createsuperuser
```

## Lancement

```powershell
python manage.py runserver
```

Application disponible sur http://127.0.0.1:8000/.

## Comptes de démo

Le projet est fourni avec deux comptes de démonstration créés via le shell :

```powershell
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); a,_=U.objects.get_or_create(username='admin', defaults={'is_staff':True,'is_superuser':True,'email':'admin@example.com'}); a.is_staff=True; a.is_superuser=True; a.set_password('admin12345!'); a.save(); c,_=U.objects.get_or_create(username='client', defaults={'email':'client@example.com'}); c.set_password('client12345!'); c.save()"
```

| Rôle | Login | Mot de passe |
|---|---|---|
| Staff / superuser | `admin` | `admin12345!` |
| Client | `client` | `client12345!` |

## Variables d'environnement

Toutes les variables sensibles sont externalisées. Voir `.env.example` pour
la liste complète.

| Variable | Défaut | Rôle |
|---|---|---|
| `DJANGO_SECRET_KEY` | clé dev (insecure) | Clé secrète Django |
| `DJANGO_DEBUG` | `true` | Active le mode debug |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hôtes autorisés (CSV) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | _(vide)_ | Origines CSRF de confiance |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | Force HTTPS en prod |
| `DJANGO_EMAIL_BACKEND` | `console` (dev) / `smtp` (prod) | Backend email |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | Config SMTP |
| `DEFAULT_FROM_EMAIL` | `Transport Console <no-reply@transport.local>` | Expéditeur |
| `DJANGO_ADMINS` | _(vide)_ | Format `Nom\|email`, séparés par `,` |

> Quand `DEBUG=False`, le module `settings.py` active automatiquement :
> `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*`, `SESSION_COOKIE_SECURE`,
> `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS=DENY`, etc.

## Tests

```powershell
python manage.py test transport -v 2
```

Suite courante : 14 tests couvrant la génération de référence, la sécurité
des CBV, l'obligation POST sur les actions livraison, l'API position et le
workflow d'annulation client.

```powershell
python manage.py check          # contrôles statiques
python manage.py check --deploy # contrôles de production
```

## Structure du projet

```
django_project/
├── config/                  # projet Django
│   ├── settings.py          # config + env vars + logging + email
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── transport/               # app métier
│   ├── models.py            # Expedition, Vehicule, Livraison, TrackingEvent
│   ├── views.py             # CBV + FBV (~530 lignes)
│   ├── forms.py             # ExpeditionForm (staff)
│   ├── client_forms.py      # ClientCommandeCreateForm / UpdateForm
│   ├── livraison_forms.py   # PlanifierLivraisonForm
│   ├── urls.py              # routes /, /expeditions/, /client/, /api/
│   ├── admin.py             # configuration de l'admin Django
│   ├── context_processors.py # alertes navbar (staff)
│   ├── notifications.py     # service d'envoi email
│   ├── signals.py           # post_save TrackingEvent → email
│   ├── apps.py              # branchement signaux dans ready()
│   ├── tests.py             # 14 tests
│   ├── management/commands/simulate_delivery.py
│   ├── migrations/
│   ├── static/css/app.css   # design system maison
│   └── templates/
│       ├── 400.html / 403.html / 404.html / 500.html
│       ├── registration/    # login + logged_out
│       └── transport/
│           ├── base.html
│           ├── home.html, dashboard.html, suivi.html
│           ├── expedition_*.html, planifier_livraison.html
│           ├── _statut_badge.html (partial)
│           ├── _pagination.html  (partial)
│           └── client/      # 6 pages espace client
├── docs/
│   └── SPECS.md             # spec de chaque page
├── logs/                    # fichiers de log (rotating)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Spécifications des pages

Voir [`docs/SPECS.md`](docs/SPECS.md) pour la spécification détaillée de
chaque page (URL, rôle, contenu, actions, permissions, états d'erreur).

## Workflow d'une expédition

```
       ┌───────────┐  client crée la commande      ┌─────────┐
START─►│ EN_ATTENTE├──────────────────────────────►│ EN_COURS│
       └─────┬─────┘  staff planifie + démarre    └────┬────┘
             │                                          │ staff
             │ client annule                            │ termine
             ▼                                          ▼
       ┌──────────┐                              ┌─────────┐
       │ ANNULEE  │                              │ LIVREE  │
       └──────────┘                              └─────────┘
```

À chaque transition, un `TrackingEvent` est créé. Le signal `post_save`
déclenche alors une notification email vers le client.

## Sécurité

- ✅ `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` lus depuis variables d'environnement
- ✅ CBV `Expedition*View` protégées (`LoginRequiredMixin` + `UserPassesTestMixin`)
- ✅ Actions de mutation en POST + `@require_POST` + CSRF
- ✅ API position (`/api/expeditions/<ref>/position/`) : `@login_required`,
  staff ou propriétaire uniquement
- ✅ Validations métier (`clean()`, `clean_<field>`) sur poids, dates,
  cohérence origine ≠ destination
- ✅ Logging fichier rotatif (5 × 5 MB) + email aux admins sur `ERROR`
- ✅ Templates d'erreur stylés (400 / 403 / 404 / 500)
- ✅ Durcissement automatique en `DEBUG=False` (HSTS, SSL redirect,
  cookies secure)

---

## Licence

Projet pédagogique — usage libre.
