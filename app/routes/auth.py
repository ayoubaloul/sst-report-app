from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import limiter
from app.models import User
from app.utils import log_action

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            log_action(user.id if user else None, None, "login_failed")
            flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
            return render_template("login.html")

        login_user(user)
        log_action(user.id, None, "login_success")
        return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    log_action(current_user.id, None, "logout")
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))
