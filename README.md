# Rapport SST – SMM Tri-K

Application web de gestion des Rapports de Dialogue Sécurité (SST), avec traçabilité,
workflow d'approbation et export CSV. Remplace le document Word statique
`Rapport_de_dialogue_sécurité.doc`.

Voir [SST_REPORT_APP_SPECS.md](SST_REPORT_APP_SPECS.md) pour les spécifications complètes.

## Stack

Flask 3.0 · SQLite · Bootstrap 5 · Python 3.12 · Flask-Login + bcrypt

## Installation

### Prérequis

```bash
python --version  # 3.12+
```

### Étapes

```bash
git clone <repo> sst-report-app
cd sst-report-app
python -m venv venv
```

Activer l'environnement virtuel :

```bash
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Copier `.env.example` vers `.env` et ajuster `SECRET_KEY` (obligatoire en production) :

```bash
cp .env.example .env
```

Initialiser la base de données (crée les tables + les 2 comptes de démonstration) :

```bash
python setup_db.py
```

## Démarrage (développement)

```bash
python run.py
```

Accès : http://localhost:5000

## Déploiement (intranet Loila/Conakry)

Le serveur de développement Flask (`python run.py`) **ne doit pas être utilisé en
production**. Utiliser `waitress`, un serveur WSGI pur Python inclus dans
`requirements.txt` :

```bash
waitress-serve --host=0.0.0.0 --port=5000 run:app
```

L'application sera accessible sur le réseau intranet via `http://smm-loila:5000`
(ou l'IP de la machine hôte).

Points à vérifier avant mise en production :
- `SECRET_KEY` dans `.env` remplacée par une valeur aléatoire et confidentielle
- Mots de passe par défaut (`password123`) changés pour alice et bob
- `app.db` sauvegardée régulièrement (fichier unique, pas de serveur DB requis)
- Le dossier du projet doit rester accessible en écriture pour SQLite
- Si un reverse proxy HTTPS est mis en place devant l'app, passer
  `SESSION_COOKIE_SECURE=True` dans `.env` (voir section Sécurité)

## Sécurité

Mesures de durcissement appliquées au-delà du MVP initial :

| Mesure | Implémentation |
|---|---|
| Sessions | Expiration après 30 min d'inactivité, cookie `HttpOnly` + `SameSite=Lax` |
| CSRF | `Flask-WTF` (`CSRFProtect`) sur tous les formulaires POST |
| Rate limiting | 5 tentatives de connexion / minute / IP (`Flask-Limiter`), GET non limité |
| Headers HTTP | `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy` sur chaque réponse |
| Contrôle d'accès | Décorateur `require_role` + vérification de propriété (un SST ne peut agir que sur ses propres rapports) |
| Validation des entrées | Longueurs maximales (section, contexte, anomalie) + valeurs Type/Cause vérifiées contre les listes autorisées |
| Audit | Connexions réussies/échouées, déconnexions, et toutes les actions sur rapport tracées dans `AuditLog` avec adresse IP |
| Secrets | `SECRET_KEY` chargée depuis `.env` (jamais commitée), voir `.gitignore` |
| Injection SQL / XSS | Déjà couvert par construction : ORM SQLAlchemy (requêtes paramétrées) + auto-échappement Jinja2 |

**Écarts volontaires par rapport au plan initial** (`SECURITY_HARDENING.md`), pour rester
proportionné à une app intranet MVP sans réécriture risquée du code déjà testé :
- CSRF implémenté via `CSRFProtect` + champ caché `csrf_token` dans les formulaires
  existants, plutôt qu'une réécriture complète en classes `FlaskForm` (WTForms)
- Rate limiting appliqué uniquement à la méthode POST de `/login` (les tentatives de
  connexion), pas au GET (consultation de la page) — évite de bloquer un utilisateur
  qui recharge simplement la page
- Pas de `default_limits` globaux sur toutes les routes (aurait pu freiner l'usage
  normal du dashboard/export par le Director)
- `SESSION_COOKIE_SECURE` configurable via `.env` plutôt que forcé à `True` en
  production : le déploiement cible (intranet Loila) est en HTTP simple, un cookie
  `Secure` y serait refusé par le navigateur et casserait la connexion
- Audit renforcé via la table `AuditLog` existante (colonne `ip_address` ajoutée)
  plutôt qu'un fichier de log séparé — cohérent avec l'objectif de traçabilité déjà
  posé en Phase 0 et consultable via `/report/<month>/history`
- Rate limiting en stockage mémoire (par défaut) : suffisant pour un déploiement
  mono-processus ; prévoir un backend partagé (Redis) si le service est un jour
  réparti sur plusieurs workers

## Comptes de démonstration

| Utilisateur | Rôle | Mot de passe |
|---|---|---|
| alice | sst_user | password123 |
| bob | director | password123 |

## Cycle de test complet (SST → Director)

1. Se connecter avec `alice` → dashboard SST
2. Cliquer "Nouveau rapport" → remplir le formulaire (section, contexte, au moins une anomalie avec Type + Cause)
3. "Enregistrer brouillon" → vérifier le message avec l'heure, recharger la page → les données sont conservées
4. "Soumettre" → le rapport passe au statut *Soumis*, disparaît de la liste éditable
5. Se déconnecter, se connecter avec `bob` → le rapport apparaît dans "Rapports soumis"
6. Cliquer "Voir" → consultation en lecture seule du rapport et de ses anomalies
7. Cliquer "Approuver" → statut *Approuvé*, message de confirmation avec date/heure
8. Cliquer "Historique" → trace des actions (Soumis, Approuvé) avec auteur et horodatage
9. Cliquer "CSV" (visible uniquement sur les rapports approuvés) → fichier téléchargé, une ligne par anomalie, encodage UTF-8 (ouverture Excel sans corruption des accents)

## URLs principales

| URL | Rôle | Fonction |
|---|---|---|
| `/` | Tous | Redirect `/login` ou `/dashboard` |
| `/login` | Tous | Formulaire de connexion |
| `/logout` | Authentifié | Déconnexion |
| `/dashboard` | sst_user, director | Dashboard personnalisé par rôle |
| `/report/new/<month>` | sst_user | Créer/éditer un brouillon (`month` = `YYYY-MM`) |
| `/report/save/<month>` | sst_user | POST — enregistrer un brouillon |
| `/report/submit/<month>` | sst_user | POST — soumettre le rapport |
| `/report/view/<month>` | sst_user, director | Consultation en lecture seule |
| `/report/approve/<month>` | director | POST — approuver un rapport soumis |
| `/report/<month>/history` | sst_user, director | Historique d'audit du rapport |
| `/report/<month>/csv` | director | Télécharger le CSV (rapport approuvé) |

## Structure du projet

```
app/
├── __init__.py       # Factory Flask
├── models.py          # User, Report, AuditLog
├── utils.py            # RBAC, audit log, export CSV
├── routes/
│   ├── auth.py          # Login/logout
│   ├── dashboard.py      # Dashboards SST/Director
│   └── report.py          # Formulaire, workflow, export
├── templates/
└── static/
config.py               # Config dev/prod
setup_db.py              # Init DB + seed utilisateurs
run.py                     # Point d'entrée (dev)
```

## Limites connues (MVP)

Voir la section "Post-MVP" des spécifications : pas d'actions correctives, pas de
notifications email, pas de rejets avec commentaires, pas de graphiques, pas de
mode hors-ligne. Le modèle de données ne conserve qu'un seul enregistrement par
rapport (un par utilisateur et par mois) — l'"historique" reflète le journal
d'audit (AuditLog), pas des versions successives du contenu.
