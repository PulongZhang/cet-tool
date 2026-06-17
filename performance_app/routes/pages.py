from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from performance_app.repositories.accounts import find_by_id, find_by_username

bp = Blueprint("pages", __name__)

ROLE_LABELS = {
    "EMPLOYEE": "员工",
    "DIRECT_MANAGER": "直接上级",
    "INDIRECT_MANAGER": "间接上级",
    "DEPT_HEAD": "部门负责人",
    "HRBP": "HRBP",
    "ADMIN": "管理员",
}

NAV_ITEMS = [
    {"title": "首页仪表盘", "href": "/", "roles": None},
    {"title": "我的自评", "href": "/self-review", "roles": {"EMPLOYEE"}},
    {"title": "直接上级评分", "href": "/direct-reports", "roles": {"DIRECT_MANAGER"}},
    {"title": "间接上级审阅", "href": "/reviews/indirect/page", "roles": {"INDIRECT_MANAGER"}},
    {"title": "部门负责人确认", "href": "/reviews/dept-head/page", "roles": {"DEPT_HEAD"}},
    {"title": "客观数据导入", "href": "/objective/import/page", "roles": {"HRBP", "ADMIN"}},
    {"title": "计算结果与导出", "href": "/results", "roles": {"HRBP", "ADMIN"}},
]


def current_page_user() -> dict | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return find_by_id(int(user_id))


def user_has_any_role(user: dict, roles: set[str] | None) -> bool:
    if roles is None:
        return True
    return bool(set(user.get("roles", [])) & roles)


def nav_items_for(user: dict | None) -> list[dict]:
    if user is None:
        return []
    return [item for item in NAV_ITEMS if user_has_any_role(user, item["roles"])]


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_page_user() is None:
            return redirect(url_for("pages.login_page", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    required = set(roles)

    def decorator(view: Callable):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_page_user()
            if user is None or not user_has_any_role(user, required):
                return render_template("forbidden.html", required_roles=sorted(required)), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.app_context_processor
def inject_page_context():
    user = current_page_user()
    return {
        "current_user": user,
        "current_roles": [ROLE_LABELS.get(role, role) for role in user.get("roles", [])] if user else [],
        "nav_items": nav_items_for(user),
    }


@bp.get("/")
@login_required
def dashboard():
    return render_template("dashboard.html")


@bp.get("/login")
def login_page():
    return render_template("login.html", next_url=request.args.get("next") or "/")


@bp.post("/login")
def login_submit():
    username = request.form.get("username")
    password = request.form.get("password")
    next_url = request.form.get("next") or "/"
    if not username or not password:
        return render_template("login.html", error="请输入用户名和密码", next_url=next_url), 400

    user = find_by_username(username)
    if user is None or user.get("status") != "ACTIVE" or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="用户名或密码错误", next_url=next_url), 401

    session.clear()
    session["user_id"] = user["id"]
    return redirect(next_url)


@bp.post("/logout")
def logout_page():
    session.clear()
    return redirect(url_for("pages.login_page"))


@bp.get("/self-review")
@role_required("EMPLOYEE")
def self_review_page():
    return render_template("self_review.html")


@bp.get("/direct-reports")
@role_required("DIRECT_MANAGER")
def direct_reports_page():
    return render_template("direct_reports.html")


@bp.get("/reviews/indirect/page")
@role_required("INDIRECT_MANAGER")
def indirect_review_page():
    return render_template("indirect_review.html")


@bp.get("/reviews/dept-head/page")
@role_required("DEPT_HEAD")
def dept_review_page():
    return render_template("dept_review.html")


@bp.get("/objective/import/page")
@role_required("HRBP", "ADMIN")
def objective_import_page():
    return render_template("objective_import.html")


@bp.get("/results")
@role_required("HRBP", "ADMIN")
def results_page():
    return render_template("results.html")
