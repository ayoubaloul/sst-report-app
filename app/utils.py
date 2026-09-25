import csv
import io
from datetime import datetime
from functools import wraps

from flask import abort, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AuditLog

CSV_HEADERS = [
    "Mois",
    "Observateur",
    "Anomalie",
    "Type",
    "Cause",
    "Status",
    "Approuvé_par",
    "Date_Approbation",
]


def require_role(role):
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return f(*args, **kwargs)

        return wrapper

    return decorator


def log_action(user_id, report_id, action):
    entry = AuditLog(
        user_id=user_id,
        report_id=report_id,
        action=action,
        ip_address=request.remote_addr,
        timestamp=datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def generate_report_csv(report, data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)

    approved_by = report.approved_by.username if report.approved_by else ""
    approved_at = (
        report.approved_at.strftime("%Y-%m-%d %H:%M") if report.approved_at else ""
    )

    for anomalie in data["anomalies"]:
        if not anomalie["anomalie"]:
            continue
        writer.writerow(
            [
                report.date_month,
                data["observateur"],
                anomalie["anomalie"],
                anomalie["type"],
                anomalie["cause"],
                report.status,
                approved_by,
                approved_at,
            ]
        )

    return "﻿" + output.getvalue()
