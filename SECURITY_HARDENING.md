# SECURITY HARDENING – Phase 4 Extension

**Objectif :** Ajouter 10 mesures de sécurité OWASP Top 10 à l'app SST Report (MVP → Production-grade)  
**Effort :** 6–8 heures  
**Tests :** Checklist incluse  
**Déploiement :** Compatible Render gratuit

---

## Résumé des Mesures

| # | Mesure | Fichier | Effort | Criticité |
|---|--------|---------|--------|-----------|
| 1 | Session timeout + Secure cookies | config.py, auth.py | 1h | **Critique** |
| 2 | HTTPS + Security headers | config.py | 0.5h | **Critique** |
| 3 | CSRF protection (Flask-WTF) | requirements.txt, forms.py, templates | 2h | **Critique** |
| 4 | Input validation stricte | forms.py | 1.5h | **Élevé** |
| 5 | Rate limiting (login brute-force) | requirements.txt, auth.py | 1.5h | **Élevé** |
| 6 | Access control + Resource ownership | report.py | 2h | **Critique** |
| 7 | Audit logging complet | models.py, utils.py | 1.5h | **Élevé** |
| 8 | Secrets en .env (pas en code) | config.py, .env.local, .gitignore | 1h | **Critique** |
| 9 | SQL injection safe (déjà ORM) | — | 0h | ✓ Déjà fait |
| 10 | XSS safe (déjà Jinja2) | — | 0h | ✓ Déjà fait |

**Total : 6–8h**

---

## STEP 1: Session Timeout + Secure Cookies

### Fichier à modifier: `config.py`

```python
# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv('.env.local')

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-prod')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
    
    # ========== SECURITY: Session timeout ==========
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)  # 30 min inactivité
    SESSION_COOKIE_SECURE = True                        # HTTPS only
    SESSION_COOKIE_HTTPONLY = True                      # Pas accessible JS
    SESSION_COOKIE_SAMESITE = 'Lax'                     # CSRF protection
    SESSION_COOKIE_NAME = '__Secure-session'            # Préfixe sécurisé
    
    # ========== SECURITY: Security headers ==========
    PREFERRED_URL_SCHEME = 'https'                      # Force HTTPS


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    # En dev : autoriser HTTP (localhost)
    SESSION_COOKIE_SECURE = False
    

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # Prod : enforcer HTTPS
    SESSION_COOKIE_SECURE = True


# Sélection config
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}

def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, DevelopmentConfig)
```

### Fichier à modifier: `app/__init__.py`

```python
# app/__init__.py
from flask import Flask, session
from datetime import timedelta
from config import get_config

def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # ========== SECURITY: Session timeout handler ==========
    @app.before_request
    def make_session_permanent():
        session.permanent = True
        app.permanent_session_lifetime = timedelta(minutes=30)
        session.modified = True
    
    # ... rest of init code (db.init_app, login_manager.init_app, etc.)
    
    return app
```

### Fichier à modifier: `app/routes/auth.py`

```python
# app/routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from app.models import User
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # ========== SECURITY: Input validation ==========
        if not username or not password:
            flash('Username et password requis', 'error')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            # ========== SECURITY: Update last login timestamp ==========
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            login_user(user, remember=False)  # remember=False = no "remember me"
            
            # ========== SECURITY: Log successful login ==========
            from app.utils import log_action
            log_action('login_success', ip_address=request.remote_addr)
            
            flash(f'Bienvenue {user.username}', 'success')
            return redirect(url_for('dashboard.dashboard'))
        else:
            # ========== SECURITY: Log failed login attempt ==========
            from app.utils import log_action
            log_action('login_failed', ip_address=request.remote_addr, 
                      details=f'username={username}')
            
            flash('Username ou password incorrect', 'error')
    
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    # ========== SECURITY: Log logout ==========
    from app.utils import log_action
    log_action('logout', ip_address=request.remote_addr)
    
    logout_user()
    flash('Déconnecté', 'success')
    return redirect(url_for('auth.login'))
```

**Checkpoint :**
```bash
# Test : Rester inactif 30 min → session timeout auto
# Vérifier logs : login_success, login_failed, logout enregistrés
```

---

## STEP 2: HTTPS + Security Headers

### Fichier à modifier: `app/__init__.py`

```python
# app/__init__.py (ajouter après create_app())

def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # ... (existing code)
    
    # ========== SECURITY: HTTP Security Headers ==========
    @app.after_request
    def set_security_headers(response):
        """Add security headers to every response"""
        
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # XSS protection (legacy, browsers have CSP now)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # HSTS (HTTP Strict Transport Security)
        # Force HTTPS for 1 year (31536000 secondes)
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains; preload'
        )
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy (strict)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        return response
    
    return app
```

**Checkpoint :**
```bash
# Test : Ouvrir DevTools (F12) → Network → Headers
# Vérifier colonnes Response : tous les headers présents
```

---

## STEP 3: CSRF Protection (Flask-WTF)

### Fichier à modifier: `requirements.txt`

```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.1        # ← AJOUTER (CSRF protection)
Werkzeug==3.0.1
python-dotenv==1.0.0
Gunicorn==21.2.0        # ← Pour déploiement (optionnel)
Flask-Limiter==3.5.0    # ← Pour rate limiting
```

```bash
# Dans Claude Code terminal
pip install -r requirements.txt
```

### Fichier à créer: `app/forms.py`

```python
# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class LoginForm(FlaskForm):
    """Login form with CSRF protection"""
    username = StringField('Username', validators=[
        DataRequired(message='Username requis'),
        Length(min=3, max=20, message='3-20 caractères')
    ])
    password = StringField('Password', validators=[
        DataRequired(message='Password requis'),
        Length(min=6, message='Min 6 caractères')
    ])
    submit = SubmitField('Connexion')


class ReportForm(FlaskForm):
    """Report form with CSRF protection"""
    date = StringField('Date', validators=[DataRequired()])
    section = StringField('Section', validators=[
        DataRequired(),
        Length(min=3, max=100)
    ])
    contexte = TextAreaField('Contexte', validators=[
        Optional(),
        Length(max=500)
    ])
    # Anomalies gérées en JSON (voir Step 4)
    submit = SubmitField('Enregistrer brouillon')
    submit_final = SubmitField('Soumettre')
```

### Fichier à modifier: `app/routes/auth.py`

```python
# app/routes/auth.py (remplacer la route /login)

from app.forms import LoginForm

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():  # ← Valide CSRF token automatiquement
        username = form.username.data.strip()
        password = form.password.data
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=False)
            log_action('login_success', ip_address=request.remote_addr)
            flash(f'Bienvenue {user.username}', 'success')
            return redirect(url_for('dashboard.dashboard'))
        else:
            log_action('login_failed', ip_address=request.remote_addr, 
                      details=f'username={username}')
            flash('Username ou password incorrect', 'error')
    
    return render_template('login.html', form=form)
```

### Fichier à modifier: `app/templates/login.html`

```html
<!-- app/templates/login.html -->
<form method="POST" novalidate>
    {{ form.hidden_tag() }}  <!-- ← CSRF token automatique -->
    
    <div class="form-group">
        {{ form.username.label }}
        {{ form.username(class="form-control") }}
        {% if form.username.errors %}
            <small class="text-danger">
                {% for error in form.username.errors %}{{ error }}{% endfor %}
            </small>
        {% endif %}
    </div>
    
    <div class="form-group">
        {{ form.password.label }}
        {{ form.password(class="form-control", type="password") }}
        {% if form.password.errors %}
            <small class="text-danger">
                {% for error in form.password.errors %}{{ error }}{% endfor %}
            </small>
        {% endif %}
    </div>
    
    {{ form.submit(class="btn btn-primary") }}
</form>
```

### Fichier à modifier: `app/templates/report_form.html`

```html
<!-- app/templates/report_form.html -->
<form method="POST" id="reportForm" novalidate>
    {{ form.hidden_tag() }}  <!-- ← CSRF token automatique -->
    
    <div class="form-group">
        {{ form.date.label }}
        {{ form.date(class="form-control", type="date") }}
    </div>
    
    <div class="form-group">
        {{ form.section.label }}
        {{ form.section(class="form-control") }}
    </div>
    
    <!-- Anomalies (tableau dynamique JS) -->
    <div id="anomalies-container">
        <!-- JS va remplir ici -->
    </div>
    
    <button type="button" class="btn btn-secondary" onclick="addAnomalyRow()">
        + Ajouter anomalie
    </button>
    
    <hr>
    {{ form.submit(class="btn btn-outline-secondary") }}
    {{ form.submit_final(class="btn btn-success") }}
</form>
```

**Checkpoint :**
```bash
# Test : Inspecter form HTML → vérifier hidden input "csrf_token" présent
# Test : POST sans csrf_token → erreur 400 "The CSRF token is missing"
```

---

## STEP 4: Input Validation Stricte

### Fichier à modifier: `app/forms.py`

```python
# app/forms.py (ajouter)

from wtforms import validators

class AnomalyForm(FlaskForm):
    """Single anomaly validation"""
    anomalie = StringField('Anomalie', validators=[
        Optional(),  # Peut être vide (ligne vide)
        Length(min=10, max=300, message='10-300 caractères')
    ])
    type_anomalie = SelectField('Type', validators=[
        Optional()
    ], choices=[
        ('', '-- Sélectionner --'),
        ('Comportement/Acte dangereux', 'Comportement/Acte dangereux'),
        ('Violation/Infraction', 'Violation/Infraction'),
        ('Condition/Situation dangereuse', 'Condition/Situation dangereuse'),
    ])
    cause = SelectField('Cause', validators=[
        Optional()
    ], choices=[
        ('', '-- Sélectionner --'),
        ('Travail - Conception', 'Travail - Conception'),
        ('Travail - Perturbations', 'Travail - Perturbations'),
        # ... (ajouter toutes les causes Annexe 2)
    ])


class ReportValidation:
    """Custom validation logic"""
    
    @staticmethod
    def validate_anomalies(anomalies_json):
        """Validate anomalies JSON"""
        import json
        
        try:
            anomalies = json.loads(anomalies_json)
        except json.JSONDecodeError:
            return False, "Erreur JSON anomalies"
        
        if not isinstance(anomalies, list):
            return False, "Anomalies doit être une liste"
        
        if len(anomalies) == 0:
            return False, "Au minimum 1 anomalie requise"
        
        if len(anomalies) > 10:
            return False, "Max 10 anomalies"
        
        for i, anomaly in enumerate(anomalies):
            # Vérifier obligatoire si anomalie saisie
            if anomaly.get('anomalie', '').strip():
                if not anomaly.get('type') or anomaly.get('type') == '':
                    return False, f"Type obligatoire pour anomalie {i+1}"
                if not anomaly.get('cause') or anomaly.get('cause') == '':
                    return False, f"Cause obligatoire pour anomalie {i+1}"
                
                # Vérifier longueur
                anomalie_text = anomaly.get('anomalie', '').strip()
                if len(anomalie_text) < 10 or len(anomalie_text) > 300:
                    return False, f"Anomalie {i+1}: 10-300 caractères"
        
        return True, None
```

### Fichier à modifier: `app/routes/report.py`

```python
# app/routes/report.py (dans @report_bp.route('/report/save/<month>', methods=['POST']))

from app.forms import ReportValidation
import json

@report_bp.route('/report/save/<month>', methods=['POST'])
@login_required
@require_role('sst_user')
def save_report(month):
    """Save report draft with validation"""
    
    try:
        data = {
            'date': request.form.get('date', '').strip(),
            'section': request.form.get('section', '').strip(),
            'contexte': request.form.get('contexte', '').strip(),
            'anomalies': request.form.get('anomalies', '[]'),
        }
        
        # ========== SECURITY: Validate date format ==========
        from datetime import datetime
        try:
            report_date = datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Format date invalide (YYYY-MM-DD)'}), 400
        
        # ========== SECURITY: Validate section ==========
        if not data['section'] or len(data['section']) < 3 or len(data['section']) > 100:
            return jsonify({'error': 'Section: 3-100 caractères'}), 400
        
        # ========== SECURITY: Validate contexte ==========
        if len(data['contexte']) > 500:
            return jsonify({'error': 'Contexte: max 500 caractères'}), 400
        
        # ========== SECURITY: Validate anomalies ==========
        is_valid, error_msg = ReportValidation.validate_anomalies(data['anomalies'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # ========== SECURITY: Check resource ownership ==========
        report = Report.query.filter_by(
            user_id=current_user.id,
            date_month=month
        ).first()
        
        if report and report.status == 'submitted':
            return jsonify({'error': 'Rapport déjà soumis, non editable'}), 403
        
        # Save
        if not report:
            report = Report(user_id=current_user.id, date_month=month)
        
        report.data_json = json.dumps(data)
        report.status = 'draft'
        db.session.add(report)
        db.session.commit()
        
        # ========== SECURITY: Log action ==========
        log_action('draft_saved', report_id=report.id, 
                  ip_address=request.remote_addr)
        
        return jsonify({'success': True, 'message': f'Brouillon enregistré {datetime.now().strftime("%H:%M")}'}), 200
        
    except Exception as e:
        app.logger.error(f"Error saving report: {str(e)}")
        return jsonify({'error': 'Erreur serveur'}), 500
```

**Checkpoint :**
```bash
# Test : Soumettre form avec anomalie < 10 chars → erreur "10-300 caractères"
# Test : Soumettre sans Type/Cause → erreur "Type obligatoire"
# Test : Soumettre + page HTML → pas persister en DB
```

---

## STEP 5: Rate Limiting (Login Brute-Force)

### Fichier à modifier: `requirements.txt`

```
Flask-Limiter==3.5.0  # ← Déjà ajouté
```

### Fichier à modifier: `app/__init__.py`

```python
# app/__init__.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # SQLite-backed storage aussi possible
)

def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # ========== SECURITY: Initialize limiter ==========
    limiter.init_app(app)
    
    # ... rest of init
    
    return app
```

### Fichier à modifier: `app/routes/auth.py`

```python
# app/routes/auth.py

from app import limiter

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # ← Rate limit: max 5 login attempts / minute
def login():
    # ... (existing code)
```

**Checkpoint :**
```bash
# Test : Essayer de login 6 fois en 1 minute → erreur 429 "Too Many Requests"
# Test : Attendre 1 min 30s → peut relancer
```

---

## STEP 6: Access Control + Resource Ownership

### Fichier à modifier: `app/routes/report.py`

```python
# app/routes/report.py
from functools import wraps
from flask import abort

def require_role(role):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@report_bp.route('/report/view/<month>')
@login_required
def view_report(month):
    """View report (SST own, Director all)"""
    report = Report.query.filter_by(date_month=month).first()
    
    if not report:
        abort(404)
    
    # ========== SECURITY: Resource ownership check ==========
    if current_user.role == 'sst_user' and report.user_id != current_user.id:
        abort(403)  # Forbidden: SST can only view own reports
    
    if current_user.role not in ['sst_user', 'director']:
        abort(403)
    
    return render_template('report_view.html', report=report)


@report_bp.route('/report/approve/<month>', methods=['POST'])
@login_required
@require_role('director')
def approve_report(month):
    """Approve report (Director only)"""
    report = Report.query.filter_by(date_month=month).first()
    
    if not report:
        abort(404)
    
    # ========== SECURITY: Prevent double-approval ==========
    if report.status != 'submitted':
        return jsonify({'error': 'Rapport ne peut pas être approuvé à ce stade'}), 400
    
    # ========== SECURITY: Verify CSRF token (WTF handles) ==========
    # (automatic with Flask-WTF)
    
    report.status = 'approved'
    report.approved_at = datetime.utcnow()
    report.approved_by_user_id = current_user.id
    db.session.commit()
    
    # ========== SECURITY: Log action ==========
    log_action('approved', report_id=report.id, 
              ip_address=request.remote_addr)
    
    return jsonify({'success': True, 'message': f'Approuvé par {current_user.username}'}), 200


@report_bp.route('/report/<month>/csv')
@login_required
@require_role('director')
def export_csv(month):
    """Export report to CSV (Director only)"""
    report = Report.query.filter_by(date_month=month).first()
    
    if not report:
        abort(404)
    
    # ========== SECURITY: Log action ==========
    log_action('csv_exported', report_id=report.id, 
              ip_address=request.remote_addr)
    
    # ... (existing CSV generation code)
    
    return send_file(...)
```

**Checkpoint :**
```bash
# Test : Login alice (sst_user) → POST /report/approve/2026-07 → erreur 403
# Test : Login alice → accès /report/view/2026-06 (autre user) → erreur 403
# Test : Login bob (director) → POST /report/approve/2026-07 → succès 200
```

---

## STEP 7: Audit Logging Complet

### Fichier à modifier: `app/models.py`

```python
# app/models.py

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'sst_user' or 'director'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # ========== SECURITY: Track logins ==========
    last_login = db.Column(db.DateTime, nullable=True)


class AuditLog(db.Model):
    """Security audit trail"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=True)
    
    # ========== SECURITY: Comprehensive logging ==========
    action = db.Column(db.String(50), nullable=False)  # 'login_success', 'login_failed', 'draft_saved', 'submitted', 'approved', 'csv_exported'
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 friendly
    user_agent = db.Column(db.String(500), nullable=True)
    details = db.Column(db.String(500), nullable=True)  # Extra details (error msg, etc)
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='audit_logs')
    report = db.relationship('Report', backref='audit_logs')
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user {self.user_id} at {self.timestamp}>'
```

### Fichier à modifier: `app/utils.py`

```python
# app/utils.py

from flask import current_app, request
from app.models import AuditLog, db
from flask_login import current_user
from datetime import datetime

def log_action(action, report_id=None, ip_address=None, details=None):
    """
    Log security action to AuditLog table
    
    Args:
        action (str): 'login_success', 'login_failed', 'draft_saved', 'submitted', 'approved', 'csv_exported'
        report_id (int, optional): Related report ID
        ip_address (str, optional): Client IP (auto-detected if None)
        details (str, optional): Extra details (error message, username, etc)
    """
    try:
        log_entry = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            report_id=report_id,
            action=action,
            ip_address=ip_address or request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500],
            details=details
        )
        db.session.add(log_entry)
        db.session.commit()
        
        current_app.logger.info(
            f"AUDIT: {action} | user={current_user.username if current_user.is_authenticated else 'anonymous'} | "
            f"report={report_id} | ip={ip_address or request.remote_addr}"
        )
    except Exception as e:
        current_app.logger.error(f"Error logging action {action}: {str(e)}")
        # Don't raise, just log - don't break app if logging fails


def get_audit_trail(report_id, limit=50):
    """Get audit trail for a report"""
    return AuditLog.query.filter_by(report_id=report_id)\
        .order_by(AuditLog.timestamp.desc())\
        .limit(limit)\
        .all()


def export_audit_csv(start_date, end_date):
    """Export full audit trail (for compliance)"""
    import csv
    from io import StringIO
    
    logs = AuditLog.query.filter(
        AuditLog.timestamp >= start_date,
        AuditLog.timestamp <= end_date
    ).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'User', 'Action', 'Report_ID', 'IP_Address', 'Details'])
    
    for log in logs:
        user_name = log.user.username if log.user else 'N/A'
        writer.writerow([
            log.timestamp.isoformat(),
            user_name,
            log.action,
            log.report_id or '',
            log.ip_address,
            log.details or ''
        ])
    
    return output.getvalue()
```

### Fichier à modifier: `app/__init__.py`

```python
# app/__init__.py

def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())
    
    # ... (existing init code)
    
    # ========== SECURITY: Logging configuration ==========
    import logging
    from logging.handlers import RotatingFileHandler
    import os
    
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler(
        'logs/sst_report.log',
        maxBytes=10_240_000,  # 10 MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    return app
```

**Checkpoint :**
```bash
# Test : Login alice → check DB AuditLog : action='login_success', user_id=1
# Test : Failed login → action='login_failed' dans AuditLog
# Test : Save draft → action='draft_saved'
# Test : Approve → action='approved'
# Test : Vérifier logs/sst_report.log existe avec entrées
```

---

## STEP 8: Secrets en .env (Pas en Code)

### Fichier à créer/modifier: `.env.local`

```bash
# .env.local (JAMAIS committer en Git)

# ========== Flask Config ==========
FLASK_ENV=production
FLASK_SECRET_KEY=your-super-secret-key-change-this-in-production-12345
DEBUG=False

# ========== Database ==========
DATABASE_URL=sqlite:///app.db

# ========== Security ==========
ALLOWED_HOSTS=sst-report.onrender.com,localhost,127.0.0.1

# ========== Session Security ==========
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
```

### Fichier à modifier: `.gitignore`

```gitignore
# .gitignore

# Environment variables
.env
.env.local
.env.*.local
.env.*.py

# Database
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# Secrets
config.local.py

# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

### Fichier à modifier: `config.py`

```python
# config.py (déjà fait, vérifier)

import os
from dotenv import load_dotenv

load_dotenv('.env.local')

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("FLASK_SECRET_KEY not set in .env.local")
    
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    DEBUG = os.getenv('DEBUG', 'False') == 'True'
```

**Checkpoint :**
```bash
# Test : ls -la | grep .env* → .env.local existant
# Test : git status → .env.local NOT in tracked files
# Test : Changer SECRET_KEY en .env.local → app redémarre OK
```

---

## STEP 9 & 10: SQL Injection + XSS (Déjà Safe)

### Vérification (pas de changements)

```python
# ✓ SAFE: ORM SQLAlchemy (parameterized queries)
user = User.query.filter_by(username=username).first()

# ✓ SAFE: Jinja2 auto-escape
{{ report.anomalie }}  <!-- HTML entities escaped automatically -->
```

**Rien à faire ici, c'est déjà sécurisé par le design.**

---

## MIGRATION DB (Ajouter Champs Audit)

### Exécuter dans terminal Claude Code

```bash
# 1. Ajouter colonnes AuditLog table
python << 'EOF'
from app import create_app, db
from app.models import AuditLog

app = create_app()
with app.app_context():
    db.create_all()
    print("✓ AuditLog table created/updated")
EOF

# 2. Ajouter colonne last_login à User
python << 'EOF'
from app import create_app, db
from app.models import User
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE user ADD COLUMN last_login DATETIME'))
        db.session.commit()
        print("✓ last_login column added")
    except:
        print("✓ last_login column already exists")
EOF
```

---

## FINAL CHECKLIST (10 Mesures)

### À exécuter après tous les changements

```bash
# 1. Vérifier dépendances
pip install -r requirements.txt

# 2. Vérifier secrets
test -f .env.local && echo "✓ .env.local existe" || echo "✗ .env.local manquant"

# 3. Vérifier .gitignore
grep ".env" .gitignore && echo "✓ .env dans .gitignore" || echo "✗ .env NOT dans .gitignore"

# 4. Redémarrer app
flask run

# 5. Tester checklist complète
```

---

## TEST CHECKLIST SÉCURITÉ

| # | Test | Étapes | Résultat attendu |
|---|------|--------|-----------------|
| 1 | Session timeout | Connexion → Inactivité 30+ min | Auto-logout + redirect /login |
| 2 | Secure cookies | DevTools → Application → Cookies | `__Secure-session` présent, Secure=✓, HttpOnly=✓ |
| 3 | HTTPS headers | DevTools → Network → Response headers | `Strict-Transport-Security`, `X-Frame-Options`, etc. |
| 4 | CSRF protection | Inspecter form login | `<input type="hidden" name="csrf_token">` présent |
| 5 | CSRF failure | POST sans token via curl | Erreur 400 "CSRF token missing" |
| 6 | Input validation | Submit form anomalie < 10 chars | Alert "10-300 caractères" |
| 7 | Rate limiting | 6 login attempts / 1 min | Erreur 429 "Too Many Requests" |
| 8 | Access control | alice login → GET /report/approve | Erreur 403 "Forbidden" |
| 9 | Resource ownership | alice → voir report de bob | Erreur 403 "Forbidden" |
| 10 | Audit logging | Login + draft save + approve | Entrées dans DB `AuditLog` + logs/sst_report.log |

---

## DEPLOYMENT RENDER (Post-Sécurité)

Une fois tous les tests OK :

```bash
# 1. Commit & Push GitHub
git add -A
git commit -m "chore: security hardening (10 measures)"
git push origin main

# 2. Créer Render.com account
# 3. Connect GitHub repo
# 4. Deploy (auto HTTPS + headers)
# 5. Set .env.local variables dans Render dashboard
```

---

## Résumé Changements

| Fichier | Type | Changements |
|---------|------|-----------|
| config.py | Modifié | Session timeouts + security headers |
| app/__init__.py | Modifié | Limiter + security headers @after_request + logging |
| app/models.py | Modifié | AuditLog table + last_login column |
| app/forms.py | Créé | LoginForm + ReportForm (Flask-WTF CSRF) |
| app/utils.py | Modifié | log_action() + get_audit_trail() + export_audit_csv() |
| app/routes/auth.py | Modifié | Rate limiting + logging + FlaskForm |
| app/routes/report.py | Modifié | Input validation + access control + resource ownership |
| app/templates/login.html | Modifié | {{ form.hidden_tag() }} for CSRF |
| app/templates/report_form.html | Modifié | {{ form.hidden_tag() }} for CSRF |
| requirements.txt | Modifié | +Flask-WTF, +Flask-Limiter |
| .env.local | Créé | Secrets non-hardcodés |
| .gitignore | Modifié | +.env* |

**Total : 12 fichiers modifiés/créés, 6–8h effort**

---

**Status :** Ready to execute in Claude Code  
**Next :** Commit Phase 4 (export CSV), THEN start Phase 5 (Security)  
**Post-Security :** Deploy to Render (Section 11 README)
