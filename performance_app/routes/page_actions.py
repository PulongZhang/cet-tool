from __future__ import annotations

from flask import Blueprint, redirect, request

from performance_app.db import get_db
from performance_app.repositories.audit import write_audit_log
from performance_app.repositories.cycles import create_cycle, delete_preparing_cycle, has_active_cycle, update_cycle_status
from performance_app.repositories.records import (
    bulk_update_status,
    list_direct_reports,
    list_scope_records,
    submit_direct_report_drafts,
    get_record,
    update_manager_score,
    update_record_field,
    update_self_review,
)
from performance_app.routes.pages import current_page_user, role_required
from performance_app.services.calculation_runner import (
    CalculationPrerequisiteError,
    adjust_final_level,
    calculate_cycle,
    finalize_cycle_results,
)
from performance_app.services.export_files import create_cycle_export
from performance_app.services.objective_import import import_objective_rows
from performance_app.services.excel_import import parse_objective_workbook

bp = Blueprint("page_actions", __name__)


def redirect_with_cycle(path: str, cycle_id: str | int | None):
    return redirect(f"{path}?cycle_id={cycle_id}" if cycle_id else path)


def form_payload(*fields: str) -> dict:
    return {field: request.form.get(field) for field in fields}


def form_cycle_id() -> int | None:
    raw_cycle_id = request.form.get("cycle_id")
    if not raw_cycle_id:
        return None
    try:
        return int(raw_cycle_id)
    except ValueError:
        return None


def current_operator() -> tuple[str, str]:
    user = current_page_user()
    return user["emp_id"], user["username"]


def write_cycle_audit(action: str, cycle: dict, operator_id: str, operator_name: str, before_snapshot: dict | None = None) -> None:
    write_audit_log(
        action=action,
        target_type="evaluation_cycle",
        target_id=cycle["id"],
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle["id"],
        before_snapshot=before_snapshot,
        after_snapshot=None if before_snapshot else cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )


@bp.post("/page/cycles/create")
@role_required("HRBP", "ADMIN")
def page_cycle_create():
    cycle_name = request.form.get("cycle_name")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    if cycle_name and start_date and end_date:
        operator_id, operator_name = current_operator()
        try:
            cycle = create_cycle(cycle_name, start_date, end_date, operator_id)
        except ValueError:
            cycle = None
        if cycle is not None:
            write_cycle_audit("CREATE_CYCLE", cycle, operator_id, operator_name)
            get_db().commit()
    return redirect("/cycles/page")


@bp.post("/page/cycles/start")
@role_required("HRBP", "ADMIN")
def page_cycle_start():
    cycle_id = form_cycle_id()
    if cycle_id is not None and not has_active_cycle(excluding_cycle_id=cycle_id):
        cycle = update_cycle_status(cycle_id, "PREPARING", "ACTIVE")
        if cycle is not None:
            operator_id, operator_name = current_operator()
            write_cycle_audit("START_CYCLE", cycle, operator_id, operator_name)
            get_db().commit()
    return redirect("/cycles/page")


@bp.post("/page/cycles/close")
@role_required("HRBP", "ADMIN")
def page_cycle_close():
    cycle_id = form_cycle_id()
    if cycle_id is not None:
        cycle = update_cycle_status(cycle_id, "ACTIVE", "CLOSED")
        if cycle is not None:
            operator_id, operator_name = current_operator()
            write_cycle_audit("CLOSE_CYCLE", cycle, operator_id, operator_name)
            get_db().commit()
    return redirect("/cycles/page")


@bp.post("/page/cycles/delete")
@role_required("HRBP", "ADMIN")
def page_cycle_delete():
    cycle_id = form_cycle_id()
    if cycle_id is not None:
        cycle = delete_preparing_cycle(cycle_id)
        if cycle is not None:
            operator_id, operator_name = current_operator()
            write_cycle_audit("DELETE_CYCLE", cycle, operator_id, operator_name, before_snapshot=cycle)
            get_db().commit()
    return redirect("/cycles/page")


@bp.post("/page/self-draft")
@role_required("EMPLOYEE")
def page_self_draft():
    record_id = int(request.form["record_id"])
    cycle_id = request.form.get("cycle_id")
    record = get_record(record_id)
    if record is not None and record["status"] in {"SELF_PENDING", "SELF_DRAFT"}:
        update_self_review(record_id, form_payload("self_summary", "self_score_1", "self_score_2", "self_score_3"), "SELF_DRAFT")
        get_db().commit()
    return redirect_with_cycle("/self-review", cycle_id)


@bp.post("/page/self-submit")
@role_required("EMPLOYEE")
def page_self_submit():
    record_id = int(request.form["record_id"])
    cycle_id = request.form.get("cycle_id")
    record = get_record(record_id)
    if record is not None and record["status"] in {"SELF_PENDING", "SELF_DRAFT"}:
        update_self_review(record_id, form_payload("self_summary", "self_score_1", "self_score_2", "self_score_3"), "DIRECT_PENDING")
        get_db().commit()
    return redirect_with_cycle("/self-review", cycle_id)


@bp.post("/page/manager-draft")
@role_required("DIRECT_MANAGER")
def page_manager_draft():
    record_id = int(request.form["record_id"])
    cycle_id = request.form.get("cycle_id")
    user = current_page_user()
    record = get_record(record_id)
    if record is not None and record["direct_manager_id"] == user["emp_id"] and record["status"] in {"DIRECT_PENDING", "DIRECT_DRAFT"}:
        update_manager_score(
            record_id,
            form_payload("manager_score_1", "manager_score_2", "manager_score_3", "manager_comment", "initial_total_grade"),
            "DIRECT_DRAFT",
        )
        get_db().commit()
    return redirect_with_cycle("/direct-reports", cycle_id)


@bp.post("/page/direct-submit")
@role_required("DIRECT_MANAGER")
def page_direct_submit():
    user = current_page_user()
    cycle_id = int(request.form["cycle_id"])
    records = list_direct_reports(cycle_id, user["emp_id"])
    blocking = [record for record in records if record["status"] != "DIRECT_DRAFT"]
    if not blocking:
        submit_direct_report_drafts(cycle_id, user["emp_id"])
        get_db().commit()
    return redirect_with_cycle("/direct-reports", cycle_id)


@bp.post("/page/record-adjustment")
@role_required("INDIRECT_MANAGER", "DEPT_HEAD")
def page_record_adjustment():
    record_id = int(request.form["record_id"])
    cycle_id = form_cycle_id()
    return_to = request.form.get("return_to") or "/"
    field_name = request.form.get("field_name")
    after_value = request.form.get("after_value")
    reason = request.form.get("reason")
    user = current_page_user()
    record = get_record(record_id)
    allowed = False
    if record is not None:
        allowed = (
            record["status"] == "INDIRECT_PENDING" and record["indirect_manager_id"] == user["emp_id"]
        ) or (
            record["status"] == "DEPT_HEAD_PENDING" and record["dept_head_id"] == user["emp_id"]
        )
    if allowed and field_name and after_value and reason:
        before_value = record.get(field_name)
        try:
            updated = update_record_field(record_id, field_name, after_value)
        except ValueError:
            updated = None
        if updated is not None:
            stage = "INDIRECT" if record["status"] == "INDIRECT_PENDING" else "DEPT_HEAD"
            write_audit_log(
                action="ADJUST_GRADE",
                target_type="evaluation_record",
                target_id=record_id,
                operator_id=user["emp_id"],
                operator_name=user["username"],
                cycle_id=record["cycle_id"],
                before_snapshot={field_name: before_value},
                after_snapshot={field_name: after_value},
                reason=reason,
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
            )
            get_db().execute(
                """
                insert into grade_adjustment_log
                    (cycle_id, record_id, stage, adjustment_type, field_name, before_value, after_value, reason, operator_id, operator_name)
                values
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["cycle_id"],
                    record_id,
                    stage,
                    "SUGGESTED_LEVEL" if field_name == "current_subjective_level" else "SUBJECTIVE_DIMENSION",
                    field_name,
                    before_value,
                    after_value,
                    reason,
                    user["emp_id"],
                    user["username"],
                ),
            )
            get_db().commit()
    return redirect_with_cycle(return_to, cycle_id)


@bp.post("/page/indirect-submit")
@role_required("INDIRECT_MANAGER")
def page_indirect_submit():
    user = current_page_user()
    cycle_id = int(request.form["cycle_id"])
    scope_records = list_scope_records(cycle_id, "indirect_manager_id", user["emp_id"])
    blocking = [record for record in scope_records if record["status"] in {"DIRECT_PENDING", "DIRECT_DRAFT", "INDIRECT_PENDING"} and record["status"] != "INDIRECT_PENDING"]
    if not blocking:
        bulk_update_status(cycle_id, "indirect_manager_id", user["emp_id"], "INDIRECT_PENDING", "DEPT_HEAD_PENDING")
        get_db().commit()
    return redirect_with_cycle("/reviews/indirect/page", cycle_id)


@bp.post("/page/dept-submit")
@role_required("DEPT_HEAD")
def page_dept_submit():
    user = current_page_user()
    cycle_id = int(request.form["cycle_id"])
    scope_records = list_scope_records(cycle_id, "dept_head_id", user["emp_id"])
    blocking = [record for record in scope_records if record["status"] in {"INDIRECT_PENDING", "DEPT_HEAD_PENDING"} and record["status"] != "DEPT_HEAD_PENDING"]
    if not blocking:
        bulk_update_status(cycle_id, "dept_head_id", user["emp_id"], "DEPT_HEAD_PENDING", "HR_PENDING")
        get_db().commit()
    return redirect_with_cycle("/reviews/dept-head/page", cycle_id)


@bp.post("/page/objective-upload")
@role_required("HRBP", "ADMIN")
def page_objective_upload():
    cycle_id = form_cycle_id()
    if cycle_id is None:
        return redirect_with_cycle("/objective/import/page", None)
    uploaded_file = request.files.get("file")
    if uploaded_file is not None and uploaded_file.filename:
        rows = parse_objective_workbook(uploaded_file)
        user = current_page_user()
        import_objective_rows(cycle_id, uploaded_file.filename or "objective.xlsx", rows, user["emp_id"], user["username"])
    return redirect_with_cycle("/objective/import/page", cycle_id)


@bp.post("/page/calculate")
@role_required("HRBP", "ADMIN")
def page_calculate():
    cycle_id = int(request.form["cycle_id"])
    user = current_page_user()
    try:
        calculate_cycle(cycle_id, user["emp_id"], user["username"])
    except CalculationPrerequisiteError:
        pass
    return redirect_with_cycle("/results", cycle_id)


@bp.post("/page/final-level")
@role_required("HRBP", "ADMIN")
def page_final_level():
    record_id = int(request.form["record_id"])
    cycle_id = request.form.get("cycle_id")
    user = current_page_user()
    adjust_final_level(record_id, request.form["final_level"], request.form["reason"], user["emp_id"], user["username"])
    return redirect_with_cycle("/results", cycle_id)


@bp.post("/page/finalize")
@role_required("HRBP", "ADMIN")
def page_finalize():
    cycle_id = int(request.form["cycle_id"])
    user = current_page_user()
    finalize_cycle_results(cycle_id, user["emp_id"], user["username"])
    return redirect_with_cycle("/results", cycle_id)


@bp.post("/page/export-final")
@role_required("HRBP", "ADMIN")
def page_export_final():
    cycle_id = int(request.form["cycle_id"])
    user = current_page_user()
    create_cycle_export(cycle_id, "final", user["emp_id"], user["username"])
    return redirect_with_cycle("/results", cycle_id)
