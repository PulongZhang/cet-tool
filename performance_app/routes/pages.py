from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import Blueprint, redirect, render_template, request, session, url_for

from performance_app.db import get_db
from werkzeug.security import check_password_hash

from performance_app.repositories.accounts import find_by_id, find_by_username
from performance_app.repositories.cycles import list_cycles
from performance_app.repositories.records import (
    distribution_for_records,
    get_my_record,
    list_direct_reports,
    list_review_records,
)
from performance_app.services.calculation_runner import list_cycle_results

bp = Blueprint("pages", __name__)

ROLE_LABELS = {
    "EMPLOYEE": "员工",
    "DIRECT_MANAGER": "直接上级",
    "INDIRECT_MANAGER": "间接上级",
    "DEPT_HEAD": "部门负责人",
    "HRBP": "HRBP",
    "ADMIN": "管理员",
}

SUBJECTIVE_LEVELS = ["A+", "A", "B+", "B", "B-", "C", "D"]

STATUS_LABELS = {
    "SELF_PENDING": "待员工自评",
    "SELF_DRAFT": "自评草稿",
    "DIRECT_PENDING": "待直接上级评分",
    "DIRECT_DRAFT": "直接上级评分草稿",
    "INDIRECT_PENDING": "待间接上级审阅",
    "DEPT_HEAD_PENDING": "待部门负责人确认",
    "HR_PENDING": "待 HR 处理",
    "INITIAL_CALCULATED": "初评已计算",
    "FINAL_CONFIRMED": "最终已确认",
    "PREPARING": "准备中",
    "ACTIVE": "进行中",
    "CLOSED": "已关闭",
}

WORKFLOW_STAGES = (
    {"title": "员工自评", "statuses": {"SELF_PENDING", "SELF_DRAFT"}},
    {"title": "直接上级评分", "statuses": {"DIRECT_PENDING", "DIRECT_DRAFT"}},
    {"title": "间接上级审阅", "statuses": {"INDIRECT_PENDING"}},
    {"title": "部门负责人确认", "statuses": {"DEPT_HEAD_PENDING"}},
    {"title": "HR 计算导出", "statuses": {"HR_PENDING", "INITIAL_CALCULATED", "FINAL_CONFIRMED"}},
)

NAV_ITEMS = [
    {"title": "首页仪表盘", "href": "/", "roles": None},
    {"title": "周期管理", "href": "/cycles/page", "roles": {"HRBP", "ADMIN"}},
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


def available_cycles() -> list[dict]:
    return list_cycles()


def selected_cycle_id() -> int | None:
    requested = request.args.get("cycle_id", type=int)
    if requested:
        return requested
    cycles = available_cycles()
    return cycles[0]["id"] if cycles else None


def selected_cycle(cycle_id: int | None) -> dict | None:
    if cycle_id is None:
        return None
    for cycle in available_cycles():
        if cycle["id"] == cycle_id:
            return cycle
    return None


def status_label(status: str | None) -> str:
    if not status:
        return "-"
    return STATUS_LABELS.get(status, status)


def workflow_progress(cycle_id: int | None, user: dict | None = None) -> dict:
    if cycle_id is None:
        return {"total": 0, "current_stage": "暂无周期", "stages": []}

    # 如果用户是直接上级，只统计该用户的下属
    if user and "DIRECT_MANAGER" in user.get("roles", []):
        rows = get_db().execute(
            """
            select r.status, count(*) as count
            from evaluation_record r
            join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
            where r.cycle_id = ? and s.direct_manager_id = ? and r.emp_id != ?
            group by r.status
            """,
            (cycle_id, user["emp_id"], user["emp_id"]),
        ).fetchall()
    else:
        # 其他角色查看全局统计
        rows = get_db().execute(
            "select status, count(*) as count from evaluation_record where cycle_id = ? group by status",
            (cycle_id,),
        ).fetchall()

    status_counts = {row["status"]: row["count"] for row in rows}
    stages = []
    for stage in WORKFLOW_STAGES:
        count = sum(status_counts.get(status, 0) for status in stage["statuses"])
        stages.append({"title": stage["title"], "count": count})
    total = sum(stage["count"] for stage in stages)
    current = next((stage for stage in stages if stage["count"]), None)
    current_stage = current["title"] if current else "暂无待处理记录"
    return {"total": total, "current_stage": current_stage, "stages": stages}


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
        "status_label": status_label,
        "subjective_levels": SUBJECTIVE_LEVELS,
    }


@bp.get("/")
@login_required
def dashboard():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    return render_template("dashboard.html", cycles=available_cycles(), cycle_id=cycle_id, progress=workflow_progress(cycle_id, user))


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


@bp.get("/cycles/page")
@role_required("HRBP", "ADMIN")
def cycle_management_page():
    return render_template("cycle_management.html", cycles=available_cycles())


@bp.get("/self-review")
@role_required("EMPLOYEE")
def self_review_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    record = get_my_record(cycle_id, user["emp_id"]) if cycle_id else None
    return render_template("self_review.html", cycles=available_cycles(), cycle_id=cycle_id, record=record)


@bp.get("/direct-reports")
@role_required("DIRECT_MANAGER")
def direct_reports_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    records = list_direct_reports(cycle_id, user["emp_id"]) if cycle_id else []
    return render_template("direct_reports.html", cycles=available_cycles(), cycle_id=cycle_id, records=records)


@bp.get("/reviews/indirect/page")
@role_required("INDIRECT_MANAGER")
def indirect_review_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    records = list_review_records(cycle_id, "indirect_manager_id", user["emp_id"], "INDIRECT_PENDING") if cycle_id else []
    return render_template(
        "indirect_review.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        records=records,
        distribution=distribution_for_records(records),
    )


@bp.get("/reviews/dept-head/page")
@role_required("DEPT_HEAD")
def dept_review_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    records = list_review_records(cycle_id, "dept_head_id", user["emp_id"], "DEPT_HEAD_PENDING") if cycle_id else []
    return render_template(
        "dept_review.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        records=records,
        distribution=distribution_for_records(records),
    )


@bp.get("/objective/import/page")
@role_required("HRBP", "ADMIN")
def objective_import_page():
    cycle_id = selected_cycle_id()
    return render_template(
        "objective_import.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        cycle=selected_cycle(cycle_id),
    )


@bp.get("/results")
@role_required("HRBP", "ADMIN")
def results_page():
    cycle_id = selected_cycle_id()
    records = list_cycle_results(cycle_id) if cycle_id else []
    return render_template("results.html", cycles=available_cycles(), cycle_id=cycle_id, records=records)
