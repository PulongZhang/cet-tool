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
    filter_records,
    final_level_distribution,
    get_my_record,
    level_range_distributions,
    list_direct_reports,
    list_records_by_statuses,
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

# 调整日志中 stage 字段的中文映射
ADJUSTMENT_STAGE_LABELS = {
    "INDIRECT": "间接上级审阅",
    "DEPT_HEAD": "部门负责人确认",
    "HR": "HR 最终调整",
}

# 调整日志中 adjustment_type 字段的中文映射
ADJUSTMENT_TYPE_LABELS = {
    "SUGGESTED_LEVEL": "建议等级调整",
    "SUBJECTIVE_DIMENSION": "主观维度调整",
    "FINAL_LEVEL": "最终等级调整",
}

# 调整日志中 field_name 字段的中文映射
FIELD_NAME_LABELS = {
    "current_subjective_level": "初评等级",
    "final_subjective_grade_1": "最终主观等级-产出和质量",
    "final_subjective_grade_2": "最终主观等级-主动承担",
    "final_subjective_grade_3": "最终主观等级-易用性和可维护",
    "final_level": "最终等级",
}

STATUS_LABELS = {
    "SELF_PENDING": "待员工自评",
    "SELF_DRAFT": "自评草稿",
    "DIRECT_PENDING": "待直接上级评分",
    "DIRECT_DRAFT": "直接上级评分草稿",
    "INDIRECT_PENDING": "待间接上级审阅",
    "DEPT_HEAD_PENDING": "待部门负责人确认",
    "HR_PENDING": "待 HR 处理",
    "INITIAL_CALCULATED": "初评",
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
    {"title": "我的自评", "href": "/self-review", "roles": {"EMPLOYEE", "DIRECT_MANAGER", "INDIRECT_MANAGER", "DEPT_HEAD"}},
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

    # 如果用户是直接上级，只统计该用户的下属（包含 EXCLUDED，因为需要打分）
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
        # 获取全部下属数
        total_row = get_db().execute(
            """
            select count(*) as count
            from evaluation_record r
            join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
            where r.cycle_id = ? and s.direct_manager_id = ? and r.emp_id != ?
            """,
            (cycle_id, user["emp_id"], user["emp_id"]),
        ).fetchone()
        total_count = total_row["count"] if total_row else 0
    else:
        # 其他角色查看全局统计（排除部门负责人和不参与计算序列）
        rows = get_db().execute(
            """
            select r.status, count(*) as count
            from evaluation_record r
            join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
            where r.cycle_id = ?
              and s.group_code != 'EXCLUDED'
              and not exists (
                  select 1 from user_role ur
                  join user_account ua on ua.id = ur.user_id
                  where ur.role_code = 'DEPT_HEAD' and ua.emp_id = r.emp_id
              )
            group by r.status
            """,
            (cycle_id,),
        ).fetchall()
        # 获取全部员工数（排除部门负责人和不参与计算序列）
        total_row = get_db().execute(
            """
            select count(*) as count
            from evaluation_record r
            join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
            where r.cycle_id = ?
              and s.group_code != 'EXCLUDED'
              and not exists (
                  select 1 from user_role ur
                  join user_account ua on ua.id = ur.user_id
                  where ur.role_code = 'DEPT_HEAD' and ua.emp_id = r.emp_id
              )
            """,
            (cycle_id,),
        ).fetchone()
        total_count = total_row["count"] if total_row else 0

    status_counts = {row["status"]: row["count"] for row in rows}
    stages = []
    for stage in WORKFLOW_STAGES:
        pending = sum(status_counts.get(status, 0) for status in stage["statuses"])
        stages.append({"title": stage["title"], "total": total_count, "pending": pending})

    # 计算当前主要阶段（找到有待办记录的第一个阶段）
    current = next((stage for stage in stages if stage["pending"] > 0), None)
    current_stage = current["title"] if current else "暂无待处理记录"
    return {"total": total_count, "current_stage": current_stage, "stages": stages}


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
    user_name = None
    if user:
        # 获取用户姓名
        from performance_app.repositories.employees import list_cycle_employees
        cycles = list_cycles()
        if cycles:
            cycle_id = cycles[0]["id"]
            employees = list_cycle_employees(cycle_id)
            for emp in employees:
                if emp["emp_id"] == user["emp_id"]:
                    user_name = emp["emp_name"]
                    break

    return {
        "current_user": user,
        "current_user_name": user_name,
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
    progress = workflow_progress(cycle_id, user)

    # 为员工角色获取员工详细信息
    employee_info = None
    if user and "EMPLOYEE" in user.get("roles", []):
        from performance_app.repositories.records import get_my_record
        employee_info = get_my_record(cycle_id, user["emp_id"]) if cycle_id else None

    # 计算各角色的待办人数和全部人数
    pending_counts = {}
    if cycle_id and user:
        from performance_app.db import get_db
        if "DIRECT_MANAGER" in user.get("roles", []):
            # 直接上级：全部下属数和待评分的下属数
            total = get_db().execute(
                """
                select count(*) from evaluation_record r
                join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
                where r.cycle_id = ? and s.direct_manager_id = ? and r.emp_id != ?
                """,
                (cycle_id, user["emp_id"], user["emp_id"]),
            ).fetchone()
            pending = get_db().execute(
                """
                select count(*) from evaluation_record r
                join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
                where r.cycle_id = ? and s.direct_manager_id = ? and r.emp_id != ?
                  and r.status in ('DIRECT_PENDING', 'DIRECT_DRAFT')
                """,
                (cycle_id, user["emp_id"], user["emp_id"]),
            ).fetchone()
            pending_counts["direct_total"] = total[0] if total else 0
            pending_counts["direct"] = pending[0] if pending else 0
        if "INDIRECT_MANAGER" in user.get("roles", []):
            # 间接上级：全部记录数和待审阅的记录数
            total = get_db().execute(
                """
                select count(*) from evaluation_record r
                join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
                where r.cycle_id = ? and s.indirect_manager_id = ? and r.emp_id != ?
                """,
                (cycle_id, user["emp_id"], user["emp_id"]),
            ).fetchone()
            pending = get_db().execute(
                """
                select count(*) from evaluation_record r
                join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
                where r.cycle_id = ? and s.indirect_manager_id = ? and r.emp_id != ?
                  and r.status = 'INDIRECT_PENDING'
                """,
                (cycle_id, user["emp_id"], user["emp_id"]),
            ).fetchone()
            pending_counts["indirect_total"] = total[0] if total else 0
            pending_counts["indirect"] = pending[0] if pending else 0
        if "DEPT_HEAD" in user.get("roles", []):
            # 部门负责人：全部记录数和待确认的记录数
            total = get_db().execute(
                """
                select count(*) from evaluation_record r
                join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
                where r.cycle_id = ? and s.dept_head_id = ? and r.emp_id != ?
                """,
                (cycle_id, user["emp_id"], user["emp_id"]),
            ).fetchone()
            pending = get_db().execute(
                """
                select count(*) from evaluation_record r
                join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
                where r.cycle_id = ? and s.dept_head_id = ? and r.emp_id != ?
                  and r.status = 'DEPT_HEAD_PENDING'
                """,
                (cycle_id, user["emp_id"], user["emp_id"]),
            ).fetchone()
            pending_counts["dept_head_total"] = total[0] if total else 0
            pending_counts["dept_head"] = pending[0] if pending else 0

    return render_template(
        "dashboard.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        progress=progress,
        employee_info=employee_info,
        pending_counts=pending_counts,
    )


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
@role_required("EMPLOYEE", "DIRECT_MANAGER", "INDIRECT_MANAGER", "DEPT_HEAD")
def self_review_page():
    from performance_app.domain.constants import (
        EMPLOYEE_LABELS, MANAGEMENT_LABELS, FORCE_MANAGEMENT_DIMENSIONS_EMPLOYEES
    )

    cycle_id = selected_cycle_id()
    user = current_page_user()
    record = get_my_record(cycle_id, user["emp_id"]) if cycle_id else None

    # 根据序列获取评价维度标签
    # 特殊人员强制使用管理维度
    if record and (user["emp_id"] in FORCE_MANAGEMENT_DIMENSIONS_EMPLOYEES or record.get("sequence") == "管理序列"):
        subjective_labels = MANAGEMENT_LABELS
    else:
        subjective_labels = EMPLOYEE_LABELS

    return render_template("self_review.html", cycles=available_cycles(), cycle_id=cycle_id, record=record, subjective_labels=subjective_labels)


@bp.get("/direct-reports")
@role_required("DIRECT_MANAGER")
def direct_reports_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    records = list_direct_reports(cycle_id, user["emp_id"]) if cycle_id else []
    # 只有存在 DIRECT_DRAFT 状态的记录时才能提交
    can_submit = any(r.get("status") == "DIRECT_DRAFT" for r in records)
    return render_template("direct_reports.html", cycles=available_cycles(), cycle_id=cycle_id, records=records, can_submit=can_submit)


@bp.get("/reviews/indirect/page")
@role_required("INDIRECT_MANAGER")
def indirect_review_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    # 获取筛选参数
    filter_status = request.args.get("filter_status", "")
    filter_level = request.args.get("filter_level", "")
    filter_level_range = request.args.get("filter_level_range", "")
    filter_dept = request.args.get("filter_dept", "")

    # 间接上级可以看到所有以自己为间接上级的员工，不管状态
    if cycle_id:
        from performance_app.repositories.records import list_scope_records, filter_records
        records = list_scope_records(cycle_id, "indirect_manager_id", user["emp_id"])
        # 应用筛选
        records = filter_records(records, filter_status, filter_level, filter_dept, filter_level_range)
    else:
        records = []
    # 只有存在 INDIRECT_PENDING 状态的记录时才能提交
    can_submit = any(r.get("status") == "INDIRECT_PENDING" for r in records)
    dist_data = level_range_distributions(records)
    return render_template(
        "indirect_review.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        records=records,
        dist_data=dist_data,
        can_submit=can_submit,
        filter_status=filter_status,
        filter_level=filter_level,
        filter_level_range=filter_level_range,
        filter_dept=filter_dept,
    )


@bp.get("/reviews/indirect/<int:record_id>")
@role_required("INDIRECT_MANAGER")
def indirect_review_detail(record_id: int):
    cycle_id = selected_cycle_id()
    user = current_page_user()
    # 获取要调整的记录详情
    from performance_app.repositories.records import get_record

    detail_record = get_record(record_id)
    if not detail_record or detail_record.get("indirect_manager_id") != user["emp_id"]:
        return "无权访问该记录", 403

    # 判断是否可编辑（只有 INDIRECT_PENDING 状态可以编辑）
    can_edit = detail_record.get("status") == "INDIRECT_PENDING"

    return render_template(
        "indirect_review_detail.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        record=detail_record,
        subjective_levels=SUBJECTIVE_LEVELS,
        can_edit=can_edit,
    )


@bp.get("/reviews/dept-head/page")
@role_required("DEPT_HEAD")
def dept_review_page():
    cycle_id = selected_cycle_id()
    user = current_page_user()
    # 部门负责人可以看到所有以自己为部门负责人的员工，不管状态
    if cycle_id:
        from performance_app.repositories.records import list_scope_records
        records = list_scope_records(cycle_id, "dept_head_id", user["emp_id"])
    else:
        records = []
    # 只有存在 DEPT_HEAD_PENDING 状态的记录时才能提交
    can_submit = any(r.get("status") == "DEPT_HEAD_PENDING" for r in records)
    dist_data = level_range_distributions(records)
    return render_template(
        "dept_review.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        records=records,
        dist_data=dist_data,
        can_submit=can_submit,
    )


@bp.get("/reviews/dept-head/<int:record_id>")
@role_required("DEPT_HEAD")
def dept_review_detail(record_id: int):
    cycle_id = selected_cycle_id()
    from performance_app.repositories.records import get_record
    from performance_app.db import get_db

    detail_record = get_record(record_id)
    if not detail_record or detail_record.get("dept_head_id") != current_page_user()["emp_id"]:
        return "无权访问该记录", 403

    # 获取完整的调整历史（用于查看各环节调整过程）
    adjustment_history = get_db().execute(
        """
        select stage, adjustment_type, field_name, before_value, after_value, reason, operator_id, operator_name, adjusted_at
        from grade_adjustment_log
        where record_id = ?
        order by adjusted_at asc
        """,
        (record_id,),
    ).fetchall()

    # 获取审计日志
    audit_logs = get_db().execute(
        """
        select action, before_snapshot, after_snapshot, operator_id, operator_name, created_at
        from audit_log
        where target_type = 'evaluation_record' and target_id = ?
        order by created_at asc
        """,
        (record_id,),
    ).fetchall()

    # 判断是否可编辑（只有 DEPT_HEAD_PENDING 状态可以编辑）
    can_edit = detail_record.get("status") == "DEPT_HEAD_PENDING"

    return render_template(
        "dept_review_detail.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        record=detail_record,
        subjective_levels=SUBJECTIVE_LEVELS,
        adjustment_history=[dict(row) for row in adjustment_history],
        audit_logs=[dict(row) for row in audit_logs],
        can_edit=can_edit,
        ADJUSTMENT_STAGE_LABELS=ADJUSTMENT_STAGE_LABELS,
        ADJUSTMENT_TYPE_LABELS=ADJUSTMENT_TYPE_LABELS,
        FIELD_NAME_LABELS=FIELD_NAME_LABELS,
    )


@bp.get("/objective/import/page")
@role_required("HRBP", "ADMIN")
def objective_import_page():
    cycle_id = selected_cycle_id()
    # 获取客观数据清单
    objective_data = []
    if cycle_id:
        from performance_app.services.objective_import import list_objective_data
        objective_data = list_objective_data(cycle_id)
    return render_template(
        "objective_import.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        cycle=selected_cycle(cycle_id),
        objective_data=objective_data,
    )


@bp.get("/results")
@role_required("HRBP", "ADMIN")
def results_page():
    cycle_id = selected_cycle_id()
    records = list_cycle_results(cycle_id) if cycle_id else []
    # 获取导出下载链接
    export_download_url = session.pop("export_download_url", None)
    export_file_name = session.pop("export_file_name", None)
    # 计算最终等级分布（基于 final_level）
    dist_data = final_level_distribution(records)
    return render_template("results.html", cycles=available_cycles(), cycle_id=cycle_id, records=records,
                          export_download_url=export_download_url, export_file_name=export_file_name,
                          dist_data=dist_data)


@bp.get("/results/adjust/<int:record_id>")
@role_required("HRBP", "ADMIN")
def final_adjust_page(record_id: int):
    """最终等级微调详情页面"""
    from performance_app.repositories.records import get_record
    from performance_app.db import get_db

    cycle_id = selected_cycle_id()
    record = get_record(record_id)

    # 获取完整的调整历史（用于查看各环节调整过程）
    adjustment_history = []
    if record:
        adjustment_history = get_db().execute(
            """
            select stage, adjustment_type, field_name, before_value, after_value, reason, operator_id, operator_name, adjusted_at
            from grade_adjustment_log
            where record_id = ?
            order by adjusted_at asc
            """,
            (record_id,),
        ).fetchall()

    # 获取审计日志
    audit_logs = []
    if record:
        audit_logs = get_db().execute(
            """
            select action, before_snapshot, after_snapshot, operator_id, operator_name, created_at
            from audit_log
            where target_type = 'evaluation_record' and target_id = ?
            order by created_at asc
            """,
            (record_id,),
        ).fetchall()

    return render_template(
        "final_adjust.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        record=record or {},
        adjustment_history=[dict(row) for row in adjustment_history],
        audit_logs=[dict(row) for row in audit_logs],
        ADJUSTMENT_STAGE_LABELS=ADJUSTMENT_STAGE_LABELS,
        ADJUSTMENT_TYPE_LABELS=ADJUSTMENT_TYPE_LABELS,
        FIELD_NAME_LABELS=FIELD_NAME_LABELS,
        SUBJECTIVE_LEVELS=SUBJECTIVE_LEVELS,
    )


# 阶段状态映射，用于路由参数验证
STAGE_STATUS_MAP = {
    "self": ["SELF_PENDING", "SELF_DRAFT"],
    "direct": ["DIRECT_PENDING", "DIRECT_DRAFT"],
    "indirect": ["INDIRECT_PENDING"],
    "dept_head": ["DEPT_HEAD_PENDING"],
    "hr": ["HR_PENDING", "INITIAL_CALCULATED", "FINAL_CONFIRMED"],
}

STAGE_LABELS = {
    "self": "员工自评",
    "direct": "直接上级评分",
    "indirect": "间接上级审阅",
    "dept_head": "部门负责人确认",
    "hr": "HR 计算导出",
}


@bp.get("/stage/<stage_name>")
@role_required("HRBP", "ADMIN")
def stage_detail_page(stage_name: str):
    """显示某个流程阶段的明细（HR/Admin专用）"""
    if stage_name not in STAGE_STATUS_MAP:
        return render_template("forbidden.html", required_roles=["HRBP", "ADMIN"], error="无效的阶段参数"), 400

    cycle_id = selected_cycle_id()
    statuses = STAGE_STATUS_MAP[stage_name]
    records = list_records_by_statuses(cycle_id, statuses) if cycle_id else []

    # 计算各状态分布
    status_counts = {}
    for record in records:
        status = record.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1

    return render_template(
        "stage_detail.html",
        cycles=available_cycles(),
        cycle_id=cycle_id,
        stage_name=stage_name,
        stage_title=STAGE_LABELS.get(stage_name, stage_name),
        records=records,
        status_counts=status_counts,
    )
