import json
import re
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AuditLog, Report
from app.utils import generate_report_csv, log_action, require_role

bp = Blueprint("report", __name__)

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

SECTION_MAX_LEN = 200
CONTEXTE_MAX_LEN = 1000
ANOMALIE_MAX_LEN = 500

ANOMALIE_TYPES = [
    "Comportement / Acte dangereux",
    "Violation / Infraction de sécurité",
    "Condition / Situation dangereuse",
]

CAUSES = {
    "A2/1 Facteurs liés au travail": [
        "Manque de logique dans la conception",
        "Perturbations constantes",
        "Instructions manquantes",
        "Matériel mal entretenu",
        "Charge de travail élevée",
        "Conditions désagréables",
    ],
    "A2/2 Facteurs liés à l'organisation": [
        "Mauvaise planification",
        "Manque de systèmes de sécurité",
        "Réponses inadéquates aux incidents",
        "Gestion basée communications descendantes",
        "Coordination insuffisante",
        "Culture SST non développée",
    ],
    "A2/3 Facteurs personnels": [
        "Description du poste inappropriée",
        "Mauvaise adaptation physique/mentale",
        "Politique de sélection absente",
        "Formation absent/inefficace",
        "Aptitude absente",
        "Surveillance médical absent",
        "Consultation SST absente",
    ],
    "A2/4 Autres facteurs": [
        "Autre (à préciser)",
    ],
}

VALID_TYPES = set(ANOMALIE_TYPES)
VALID_CAUSES = {c for group in CAUSES.values() for c in group}


def _validate_month(month):
    if not MONTH_RE.match(month):
        abort(404)


def _default_data(month, username):
    return {
        "date": f"{month}-01",
        "section": "",
        "observateur": username,
        "contexte": "",
        "anomalies": [
            {"n": i, "anomalie": "", "type": "", "cause": ""} for i in range(1, 6)
        ],
    }


def _parse_form_data(form, username):
    anomalies = []
    for i in range(1, 6):
        anomalies.append(
            {
                "n": i,
                "anomalie": form.get(f"anomalie_{i}", "").strip(),
                "type": form.get(f"type_{i}", "").strip(),
                "cause": form.get(f"cause_{i}", "").strip(),
            }
        )
    return {
        "date": form.get("date", "").strip(),
        "section": form.get("section", "").strip(),
        "observateur": username,
        "contexte": form.get("contexte", "").strip(),
        "anomalies": anomalies,
    }


def _validate_data(data, require_full):
    errors = []
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except ValueError:
        errors.append("Date invalide.")

    if len(data["section"]) > SECTION_MAX_LEN:
        errors.append(f"Section : {SECTION_MAX_LEN} caractères maximum.")
    if len(data["contexte"]) > CONTEXTE_MAX_LEN:
        errors.append(f"Contexte : {CONTEXTE_MAX_LEN} caractères maximum.")

    for a in data["anomalies"]:
        if len(a["anomalie"]) > ANOMALIE_MAX_LEN:
            errors.append(
                f"Ligne {a['n']} : anomalie limitée à {ANOMALIE_MAX_LEN} caractères."
            )
        if a["type"] and a["type"] not in VALID_TYPES:
            errors.append(f"Ligne {a['n']} : type invalide.")
        if a["cause"] and a["cause"] not in VALID_CAUSES:
            errors.append(f"Ligne {a['n']} : cause invalide.")
        if require_full and a["anomalie"] and (not a["type"] or not a["cause"]):
            errors.append(f"Ligne {a['n']} : Type et Cause sont obligatoires.")
    return errors


def _render_form(data, month):
    return render_template(
        "report_form.html",
        data=data,
        month=month,
        anomalie_types=ANOMALIE_TYPES,
        causes=CAUSES,
    )


@bp.route("/report/new/<month>")
@require_role("sst_user")
def new_report(month):
    _validate_month(month)
    existing = Report.query.filter_by(user_id=current_user.id, date_month=month).first()

    if existing and existing.status != "draft":
        return redirect(url_for("report.view_report", month=month))

    data = json.loads(existing.data_json) if existing else _default_data(month, current_user.username)
    return _render_form(data, month)


@bp.route("/report/save/<month>", methods=["POST"])
@require_role("sst_user")
def save_report(month):
    _validate_month(month)
    existing = Report.query.filter_by(user_id=current_user.id, date_month=month).first()

    if existing and existing.status != "draft":
        flash("Ce rapport a déjà été soumis et ne peut plus être modifié.", "danger")
        return redirect(url_for("dashboard.index"))

    data = _parse_form_data(request.form, current_user.username)
    errors = _validate_data(data, require_full=False)
    if errors:
        for e in errors:
            flash(e, "danger")
        return _render_form(data, month)

    if existing:
        existing.data_json = json.dumps(data, ensure_ascii=False)
        report = existing
    else:
        report = Report(
            user_id=current_user.id,
            date_month=month,
            status="draft",
            data_json=json.dumps(data, ensure_ascii=False),
        )
        db.session.add(report)
    db.session.commit()
    log_action(current_user.id, report.id, "draft_saved")

    flash(f"Brouillon enregistré {datetime.now().strftime('%H:%M')}", "success")
    return redirect(url_for("report.new_report", month=month))


@bp.route("/report/submit/<month>", methods=["POST"])
@require_role("sst_user")
def submit_report(month):
    _validate_month(month)
    existing = Report.query.filter_by(user_id=current_user.id, date_month=month).first()

    if existing and existing.status != "draft":
        flash("Ce rapport a déjà été soumis.", "danger")
        return redirect(url_for("dashboard.index"))

    data = _parse_form_data(request.form, current_user.username)
    errors = _validate_data(data, require_full=True)
    if errors:
        for e in errors:
            flash(e, "danger")
        return _render_form(data, month)

    if existing:
        existing.data_json = json.dumps(data, ensure_ascii=False)
        existing.status = "submitted"
        existing.submitted_at = datetime.utcnow()
        report = existing
    else:
        report = Report(
            user_id=current_user.id,
            date_month=month,
            status="submitted",
            data_json=json.dumps(data, ensure_ascii=False),
            submitted_at=datetime.utcnow(),
        )
        db.session.add(report)
    db.session.commit()
    log_action(current_user.id, report.id, "submitted")

    flash("Rapport soumis avec succès.", "success")
    return redirect(url_for("dashboard.index"))


@bp.route("/report/view/<month>")
@login_required
def view_report(month):
    _validate_month(month)

    if current_user.is_director():
        user_id = request.args.get("user", type=int)
        if not user_id:
            abort(404)
        report = Report.query.filter_by(user_id=user_id, date_month=month).first_or_404()
        if report.status not in ("submitted", "approved"):
            abort(404)
    else:
        report = Report.query.filter_by(
            user_id=current_user.id, date_month=month
        ).first_or_404()

    data = json.loads(report.data_json)
    return render_template("report_view.html", report=report, data=data)


@bp.route("/report/approve/<month>", methods=["POST"])
@require_role("director")
def approve_report(month):
    _validate_month(month)
    user_id = request.form.get("user_id", type=int)
    if not user_id:
        abort(400)

    report = Report.query.filter_by(user_id=user_id, date_month=month).first_or_404()
    if report.status != "submitted":
        flash("Ce rapport ne peut pas être approuvé (statut invalide).", "danger")
        return redirect(url_for("dashboard.index"))

    report.status = "approved"
    report.approved_at = datetime.utcnow()
    report.approved_by_user_id = current_user.id
    db.session.commit()
    log_action(current_user.id, report.id, "approved")

    flash(
        f"Approuvé par {current_user.username} le "
        f"{report.approved_at.strftime('%d/%m/%Y %H:%M')}",
        "success",
    )
    return redirect(url_for("dashboard.index"))


@bp.route("/report/<month>/history")
@login_required
def report_history(month):
    _validate_month(month)

    if current_user.is_director():
        user_id = request.args.get("user", type=int)
        if not user_id:
            abort(404)
        report = Report.query.filter_by(user_id=user_id, date_month=month).first_or_404()
    else:
        report = Report.query.filter_by(
            user_id=current_user.id, date_month=month
        ).first_or_404()

    logs = (
        AuditLog.query.filter_by(report_id=report.id)
        .order_by(AuditLog.timestamp)
        .all()
    )
    return render_template("report_history.html", report=report, logs=logs)


@bp.route("/report/<month>/csv")
@require_role("director")
def export_csv(month):
    _validate_month(month)
    user_id = request.args.get("user", type=int)
    if not user_id:
        abort(404)

    report = Report.query.filter_by(user_id=user_id, date_month=month).first_or_404()
    if report.status != "approved":
        abort(404)

    data = json.loads(report.data_json)
    csv_content = generate_report_csv(report, data)

    response = Response(csv_content, mimetype="text/csv")
    filename = f"rapport_{report.date_month}_{data['observateur']}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
