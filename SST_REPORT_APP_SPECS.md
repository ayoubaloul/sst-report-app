# SST Report App – Spécifications MVP

**Projet :** Rapport de Dialogue Sécurité (Rapport SST) – SMM Tri-K  
**Client :** Équipe SST + Direction  
**Stack :** Flask 3.0 + SQLite + Bootstrap 5 + Python 3.12  
**Timeline :** 3–4 jours (MVP soft launch)  
**Deployment :** Loila/Conakry intranet (http://localhost:5000 local, http://smm-loila:5000 intranet)

---

## 1. CONTEXTE & OBJECTIFS

### Problème
Actuellement, rapports SST (Rapport_de_dialogue_sécurité.doc) = document Word static.
- Pas de traçabilité (qui a modifié, quand)
- Pas de contrôle d'accès (SST remplit, Direction voit tout)
- Pas d'historique versionné
- Pas d'export structuré pour compliance

### Solution
Application web Flask simple : **traçabilité + workflows + exports**.

### Workflows
```
SST User:
  1. Accès dashboard (liste ses rapports)
  2. Remplit formulaire → sauve brouillon (draft)
  3. Soumet (submitted)
  4. Voit statut approbation

Director:
  1. Accès dashboard (liste TOUS rapports soumis/approuvés)
  2. Consulte rapport (read-only)
  3. Approuve (approved, timestamp + user_id)
  4. Exporte CSV/PDF pour archives
```

### Besoins non-fonctionnels
- **Traçabilité :** AuditLog chaque action (submit, approve, reject)
- **Offline-ready :** SQLite local (pas de dépendance réseau)
- **Compliance :** CSV export avec audit trail pour audit externe
- **Performance :** < 1s load page (< 10 rapports en DB initialement)

---

## 2. ARCHITECTURE TECHNIQUE

### Tech Stack
| Composant | Technologie | Version |
|-----------|-------------|---------|
| Backend | Flask | 3.0+ |
| DB | SQLite | Native |
| Frontend | Bootstrap 5 + Vanilla JS | 5.3 |
| Auth | Flask-Login + bcrypt | — |
| Templating | Jinja2 | Native Flask |
| Python | — | 3.12 |

### Modèle Données (Minimal)
```
User
├─ id (int, primary key)
├─ username (str, unique)
├─ password_hash (str, bcrypt)
├─ role (str: 'sst_user' | 'director')
└─ created_at (datetime)

Report
├─ id (int, primary key)
├─ user_id (int, FK → User)
├─ date_month (str: 'YYYY-MM')
├─ status (str: 'draft' | 'submitted' | 'approved')
├─ data_json (str: JSON serialisé du formulaire)
├─ submitted_at (datetime, nullable)
├─ approved_at (datetime, nullable)
├─ approved_by_user_id (int, FK → User, nullable)
└─ created_at (datetime)

AuditLog
├─ id (int, primary key)
├─ user_id (int, FK → User)
├─ report_id (int, FK → Report)
├─ action (str: 'draft_saved' | 'submitted' | 'approved')
└─ timestamp (datetime)
```

### Structure Projet
```
sst-report-app/
├── app/
│   ├── __init__.py              # Factory Flask + init DB
│   ├── models.py                # User, Report, AuditLog (SQLAlchemy)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py              # Login/Logout, RBAC decorator
│   │   ├── dashboard.py         # Dashboard SST/Director
│   │   └── report.py            # Formulaire, sauvegarde, approbation, export
│   ├── templates/
│   │   ├── base.html            # Header, nav, footer
│   │   ├── login.html           # Form login
│   │   ├── dashboard.html       # Liste rapports (SST ou Director)
│   │   ├── report_form.html     # Formulaire remplissage
│   │   ├── report_view.html     # Consultation (read-only)
│   │   └── report_history.html  # Historique versions
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css        # Custom CSS (minimal)
│   │   └── js/
│   │       └── form.js          # Validation JS formulaire
│   └── utils.py                 # Helpers (export CSV, audit log)
├── migrations/                  # (Optional: Alembic, ou simple init)
├── config.py                    # Config dev/prod, secrets
├── requirements.txt             # Dépendances Python
├── setup_db.py                  # Init DB + seed users
├── run.py                       # Entry point Flask
└── README.md                    # Instructions déploiement
```

---

## 3. BACKLOG MVP (Phases)

### Phase 0: Infrastructure (Jour 1, 4–5h)

| ID | Feature | Spec | Effort |
|----|---------|------|--------|
| **0.1** | Stack de base | Flask app factory, config dev/prod, .env | 1.5h |
| **0.2** | Modèles SQLAlchemy | User, Report, AuditLog avec relations | 1.5h |
| **0.3** | DB init + seed | setup_db.py crée tables + 2 users (alice/sst_user, bob/director) | 1h |
| **0.4** | Repo structure | Dossiers templates/, static/, routes/ + __init__.py | 0.5h |

**Checkpoints :**
- `python setup_db.py` → DB créée sans erreur
- `sqlite3 app.db "SELECT * FROM user;"` → alice et bob présents

---

### Phase 1: Auth + Dashboard (Jour 1–2, 4–5h)

| ID | Feature | Spec | Effort |
|----|---------|------|--------|
| **1.1** | Login/Logout | Route GET `/login` (form), POST validation bcrypt. Redirect `/dashboard` après succès. | 2h |
| **1.2** | Décorateur RBAC | `@require_role('sst_user')` / `@require_role('director')` + `@login_required`. Redirect 403 si forbidden. | 1h |
| **1.3** | Dashboard SST | Route `/dashboard` (sst_user) : liste ses rapports (draft + submitted). Colonnes : Mois \| Statut \| Actions [Éditer, Voir]. | 1.5h |
| **1.4** | Dashboard Director | Route `/dashboard` (director) : liste TOUS rapports submitted/approved. Colonnes : Mois \| Observateur \| Statut \| Action [Approuver, Voir]. | 1.5h |

**Checkpoints :**
- Login alice (sst_user) → redirect /dashboard SST
- Login bob (director) → redirect /dashboard Director
- Alice ne voit que ses rapports; bob voit tous

---

### Phase 2: Formulaire Minimaliste (Jour 2–3, 5h)

| ID | Feature | Spec | Effort |
|----|---------|------|--------|
| **2.1** | GET `/report/new/{month}` | Formulaire vierge pré-rempli : Date (date picker = 1er du mois), Section (text), Observateur (read-only = session user), Contexte (textarea). | 1.5h |
| **2.2** | Tableau anomalies | 5 lignes vides. Colonnes : N° (auto 1–5), Anomalie (textarea), Type (dropdown = Annexe 1: Comportement/Violation/Condition), Cause (dropdown = Annexe 2: Travail/Organisation/Personnel/Autre). | 2h |
| **2.3** | Validation (JS + Backend) | Frontend : Type + Cause obligatoires si Anomalie non-vide. Backend POST : idem + vérification date valide. Alert si erreur. | 1h |
| **2.4** | Draft + Submit | Deux boutons : "Enregistrer brouillon" (POST `/report/save/{month}`, status=draft), "Soumettre" (POST `/report/submit/{month}`, status=submitted). Message flash succès. | 1.5h |

**Checkpoints :**
- Remplir formulaire, cliquer "Enregistrer brouillon" → message "Brouillon enregistré 14:23"
- Revenir au formulaire → données reprises (pas perdu)
- Cliquer "Soumettre" → status passe à submitted, aparition dans dashboard director

---

### Phase 3: Workflow Approbation + Audit (Jour 3–4, 4h)

| ID | Feature | Spec | Effort |
|----|---------|------|--------|
| **3.1** | Vue consultation (Director) | Route GET `/report/view/{month}` : affiche rapport submitted en read-only. Tableau anomalies complet visible, pas editable. | 1h |
| **3.2** | Approbation | Bouton "Approuver" (visible si status=submitted) → POST `/report/approve/{month}` : status → approved, approved_at timestamp, approved_by_user_id = bob. Redirection dashboard. Message "Approuvé par [bob] le [date]". | 1h |
| **3.3** | Historique versions | Lien "Historique" sur report → affiche list [Version#, Date_Soumission, Status, Approuvé_par, Date_Approbation]. Click version → affiche rapport read-only pour cette version. | 1.5h |
| **3.4** | AuditLog auto | Chaque action (draft_saved, submitted, approved) → insérer ligne AuditLog (user_id, report_id, action, timestamp). Pas de before/after JSON (trop complexe MVP). | 0.5h |

**Checkpoints :**
- Alice soumet rapport → status=submitted, submitted_at = now
- Bob voit rapport dans son dashboard
- Bob clique "Approuver" → status=approved, approved_at = now, approved_by_user_id=bob
- Alice voit historique → affiche soumission + approbation

---

### Phase 4: Export + Finale (Jour 4, 2–3h)

| ID | Feature | Spec | Effort |
|----|---------|------|--------|
| **4.1** | Export CSV | Bouton "Télécharger CSV" sur rapport approved. CSV : [Mois, Observateur, Anomalie, Type, Cause, Status, Approuvé_par, Date_Approbation]. Encoding UTF-8, séparateur `,`. | 1.5h |
| **4.2** | Test complet + docs | Tests manuels : cycle complet SST → Director. README avec instructions démarrage + déploiement. | 1.5h |

**Checkpoints :**
- Exporter rapport → fichier CSV téléchargé, ouverture Excel sans corruption
- README contient : dépendances, setup_db.py, flask run, URLs

---

## 4. FORMULAIRE STRUCTURE (JSON)

Forme sérialisée en `data_json` dans DB :

```json
{
  "date": "2026-10-06",
  "section": "BUREAU BOM",
  "observateur": "alice",
  "contexte": "Elaboration du Rapport",
  "anomalies": [
    {
      "n": 1,
      "anomalie": "Non arrangement du poste de travail",
      "type": "Condition dangereuse",
      "cause": "Manque de logique dans la conception"
    },
    {
      "n": 2,
      "anomalie": "Utilisation abusive des rallonges Electrique",
      "type": "Comportement dangereux",
      "cause": "Mauvaise application de la procédure"
    }
  ]
}
```

---

## 5. DROPDOWNS ANNEXES

### Annexe 1: Type d'anomalie
```
[ ] Comportement / Acte dangereux
    [ ] Manque de concentration
    [ ] Mauvaise application de la procédure
[ ] Violation / Infraction de sécurité
    [ ] Routinière
    [ ] Situationnelle
    [ ] Exceptionnelle
[ ] Condition / Situation Dangereuse
```

### Annexe 2: Causes racines
```
A2/1 Facteurs liés au travail:
    - Manque de logique dans la conception
    - Perturbations constantes
    - Instructions manquantes
    - Matériel mal entretenu
    - Charge de travail élevée
    - Conditions désagréables

A2/2 Facteurs liés à l'organisation:
    - Mauvaise planification
    - Manque de systèmes de sécurité
    - Réponses inadéquates aux incidents
    - Gestion basée communications descendantes
    - Coordination insuffisante
    - Culture SST non développée

A2/3 Facteurs personnels:
    - Description du poste inappropriée
    - Mauvaise adaptation physique/mentale
    - Politique de sélection absente
    - Formation absent/inefficace
    - Aptitude absente
    - Surveillance médical absent
    - Consultation SST absente

A2/4 Autres facteurs:
    - [à préciser]
```

---

## 6. DÉMARRAGE RAPIDE

### Prerequis
```bash
python --version  # 3.12+
pip --version
```

### Step 1: Init repo
```bash
mkdir sst-report-app && cd sst-report-app
git init
python -m venv venv
source venv/bin/activate  # Mac/Linux
# OU
venv\Scripts\activate     # Windows
```

### Step 2: Dépendances
Créer `requirements.txt` :
```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Werkzeug==3.0.1
python-dotenv==1.0.0
```

```bash
pip install -r requirements.txt
```

### Step 3: Init DB
```bash
python setup_db.py
# Sortie : "Database initialized. Users: alice (sst_user), bob (director)"
```

### Step 4: Démarrer app
```bash
flask run
# Accès : http://localhost:5000
```

### Step 5: Test
- Login alice / pw (défaut: "password123" en seed)
- Remplir formulaire, sauver brouillon
- Logout, login bob
- Voir rapport, approuver
- Export CSV

---

## 7. POINTS DE TEST (Checklist MVP)

| Test | Étape | Résultat attendu |
|------|-------|-----------------|
| **Auth** | Login alice | Dashboard SST chargé |
| **Auth** | Login bob | Dashboard Director chargé |
| **Auth** | Accès /report/new sans login | Redirect /login |
| **Form** | Remplir 2 anomalies, cliquer "Enregistrer brouillon" | Message flash "Enregistré", data_json en DB |
| **Form** | Revenir à /report/new/{month} | Données reprises (pas vide) |
| **Form** | Cliquer "Soumettre" sans Type anomalie | Alert JS "Type obligatoire" |
| **Workflow** | Alice soumet, logout | status=submitted, submitted_at=now |
| **Workflow** | Bob login, voit rapport | Dashboard Director affiche rapport d'Alice |
| **Workflow** | Bob clique "Approuver" | status=approved, approved_at=now, AuditLog inséré |
| **History** | Cliquer "Historique" sur rapport | Affiche 2 versions (submitted, approved) |
| **Export** | Cliquer "Télécharger CSV" | Fichier .csv reçu, colonnes bonnes |
| **Performance** | Page charge | < 1s |

---

## 8. DONNÉES DE DÉPLOIEMENT

### Users seed
```
Utilisateur 1:
  username: alice
  role: sst_user
  password: password123

Utilisateur 2:
  username: bob
  role: director
  password: password123
```

### URLs Principales
| URL | Rôle | Fonction |
|-----|------|----------|
| `/` | Tous | Redirect /login ou /dashboard |
| `/login` | Tous | Form auth |
| `/logout` | Authentifié | Logout + redirect /login |
| `/dashboard` | sst_user, director | Dashboard personnalisé |
| `/report/new/{month}` | sst_user | Formulaire création |
| `/report/view/{month}` | director | Consultation read-only |
| `/report/save/{month}` | sst_user | POST brouillon |
| `/report/submit/{month}` | sst_user | POST soumission |
| `/report/approve/{month}` | director | POST approbation |
| `/report/{month}/history` | director | Historique versions |
| `/report/{month}/csv` | director | Télécharger CSV |

---

## 9. POINTS DE VIGILANCE

| Risque | Mitigation |
|--------|-----------|
| **Perte de données brouillon** | AuditLog chaque save (draft_saved action), UI message confirmation |
| **Modification après soumission** | Form disabled POST submit, status=submitted → form non editable |
| **Accès non autorisé** | Décorateur @require_role strict, vérifier report.user_id = session.user_id pour SST |
| **DB corruption** | setup_db.py = script idempotent (check IF NOT EXISTS tables) |
| **Performance** | SQLite OK pour MVP (< 50 rapports/an). Pas d'index requis. |

---

## 10. POST-MVP (NOT INCLUDED)

- Actions immédiates + correctives (view séparée pour SST+Director)
- Recommandations libres
- Rejets avec commentaires
- Notifications email
- Graphiques anomalies/mois (Chart.js)
- Mobile responsive
- Offline mode (Service Worker)

---

## Próximo Paso

1. **Créer tous les fichiers** (run.py, app/__init__.py, models.py, routes/*, templates/*)
2. **Tester Phase 0** : `python setup_db.py` + `flask run`
3. **Tester Phase 1** : Login alice/bob
4. **Tester Phase 2** : Remplir formulaire
5. **Tester Phase 3** : Approbation workflow
6. **Tester Phase 4** : Export CSV
7. **Validation complète** : Checklist tests
8. **Déploiement Loila** : Instructions README + deployment notes

---

**Status :** Ready for Claude Code launch  
**Created :** 2026-09-25  
**Version :** 1.0 MVP Specs
