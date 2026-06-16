from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)


@bp.get("/")
def dashboard():
    return render_template("dashboard.html")


@bp.get("/login")
def login_page():
    return render_template("login.html")


@bp.get("/self-review")
def self_review_page():
    return render_template("self_review.html")


@bp.get("/direct-reports")
def direct_reports_page():
    return render_template("direct_reports.html")


@bp.get("/reviews/indirect/page")
def indirect_review_page():
    return render_template("indirect_review.html")


@bp.get("/reviews/dept-head/page")
def dept_review_page():
    return render_template("dept_review.html")


@bp.get("/objective/import/page")
def objective_import_page():
    return render_template("objective_import.html")


@bp.get("/results")
def results_page():
    return render_template("results.html")
