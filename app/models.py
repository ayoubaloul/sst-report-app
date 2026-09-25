from datetime import datetime

import bcrypt
from flask_login import UserMixin

from app.extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'sst_user' | 'director'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    reports = db.relationship(
        "Report", foreign_keys="Report.user_id", back_populates="author"
    )

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def is_director(self):
        return self.role == "director"

    def is_sst_user(self):
        return self.role == "sst_user"

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Report(db.Model):
    __tablename__ = "report"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_month = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    status = db.Column(
        db.String(20), nullable=False, default="draft"
    )  # 'draft' | 'submitted' | 'approved'
    data_json = db.Column(db.Text, nullable=False, default="{}")
    submitted_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    author = db.relationship(
        "User", foreign_keys=[user_id], back_populates="reports"
    )
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id])
    audit_logs = db.relationship(
        "AuditLog", back_populates="report", order_by="AuditLog.timestamp"
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "date_month", name="uq_report_user_month"),
    )

    def __repr__(self):
        return f"<Report {self.date_month} user={self.user_id} status={self.status}>"


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"), nullable=True)
    action = db.Column(
        db.String(20), nullable=False
    )  # 'draft_saved' | 'submitted' | 'approved' | 'login_success' | 'login_failed' | 'logout'
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
    report = db.relationship("Report", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.action} report={self.report_id} user={self.user_id}>"
