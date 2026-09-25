from datetime import date

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import Report

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    current_month = date.today().strftime("%Y-%m")

    if current_user.is_director():
        reports = (
            Report.query.filter(Report.status.in_(["submitted", "approved"]))
            .order_by(Report.date_month.desc())
            .all()
        )
        return render_template(
            "dashboard.html", reports=reports, current_month=current_month
        )

    reports = (
        Report.query.filter_by(user_id=current_user.id)
        .filter(Report.status.in_(["draft", "submitted"]))
        .order_by(Report.date_month.desc())
        .all()
    )
    return render_template(
        "dashboard.html", reports=reports, current_month=current_month
    )
