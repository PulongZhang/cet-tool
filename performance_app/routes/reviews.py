from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.db import get_db
from performance_app.domain.workflow import withdraw_status
from performance_app.repositories.audit import write_audit_log
from performance_app.repositories.records import (
    bulk_update_status,
    distribution_for_records,
    get_record,
    list_review_records,
    list_scope_records,
    update_record_field,
    update_status,
)
from performance_app.routes.records import CYCLE_ID_REQUIRED, current_user_or_response

bp = Blueprint("reviews", __name__)


def cycle_id_from_request() -> int | None:
    return request.args.get("cycle_id", type=int) or (request.get_json(silent=True) or {}).get("cycle_id")


def blocking_records(records: list[dict], expected_status: str, relevant_statuses: set[str]) -> list[dict]:
    return [
        {"record_id": record["id"], "emp_id": record["emp_id"], "status": record["status"]}
        for record in records
        if record["status"] in relevant_statuses and record["status"] != expected_status
    ]


@bp.get("/reviews/indirect")
def indirect_reviews():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = cycle_id_from_request()
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    records = list_review_records(cycle_id, "indirect_manager_id", user["emp_id"], "INDIRECT_PENDING")
    return jsonify({"records": records})


@bp.get("/reviews/indirect/distribution")
def indirect_distribution():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = cycle_id_from_request()
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    records = list_review_records(cycle_id, "indirect_manager_id", user["emp_id"], "INDIRECT_PENDING")
    return jsonify({"distribution": distribution_for_records(records)})


@bp.post("/reviews/indirect/submit")
def indirect_submit():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = cycle_id_from_request()
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    scope_records = list_scope_records(cycle_id, "indirect_manager_id", user["emp_id"])
    blocking = blocking_records(scope_records, "INDIRECT_PENDING", {"DIRECT_PENDING", "DIRECT_DRAFT", "INDIRECT_PENDING"})
    if blocking:
        return jsonify({"error": "not all scoped records are ready to submit", "blocking_records": blocking}), 409
    updated = bulk_update_status(cycle_id, "indirect_manager_id", user["emp_id"], "INDIRECT_PENDING", "DEPT_HEAD_PENDING")
    get_db().commit()
    return jsonify({"updated_count": updated})


@bp.get("/reviews/dept-head")
def dept_head_reviews():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = cycle_id_from_request()
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    records = list_review_records(cycle_id, "dept_head_id", user["emp_id"], "DEPT_HEAD_PENDING")
    return jsonify({"records": records})


@bp.get("/reviews/dept-head/distribution")
def dept_head_distribution():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = cycle_id_from_request()
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    records = list_review_records(cycle_id, "dept_head_id", user["emp_id"], "DEPT_HEAD_PENDING")
    return jsonify({"distribution": distribution_for_records(records)})


@bp.post("/reviews/dept-head/submit")
def dept_head_submit():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = cycle_id_from_request()
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    scope_records = list_scope_records(cycle_id, "dept_head_id", user["emp_id"])
    blocking = blocking_records(scope_records, "DEPT_HEAD_PENDING", {"INDIRECT_PENDING", "DEPT_HEAD_PENDING"})
    if blocking:
        return jsonify({"error": "not all scoped records are ready to submit", "blocking_records": blocking}), 409
    updated = bulk_update_status(cycle_id, "dept_head_id", user["emp_id"], "DEPT_HEAD_PENDING", "HR_PENDING")
    get_db().commit()
    return jsonify({"updated_count": updated})


@bp.post("/records/<int:record_id>/adjustments")
def add_adjustment(record_id: int):
    user, error = current_user_or_response()
    if error:
        return error
    record = get_record(record_id)
    if record is None:
        return jsonify({"error": "record not found"}), 404
    # 检查权限：只有状态为INDIRECT_PENDING的间接上级或DEPT_HEAD_PENDING的部门负责人可以调整
    allowed = (
        record.get("status") == "INDIRECT_PENDING" and record.get("indirect_manager_id") == user["emp_id"]
    ) or (
        record.get("status") == "DEPT_HEAD_PENDING" and record.get("dept_head_id") == user["emp_id"]
    )
    if not allowed:
        return jsonify({"error": "not authorized to adjust this record in current status"}), 403
    payload = request.get_json(silent=True) or {}
    field_name = payload.get("field_name")
    after_value = payload.get("after_value")
    reason = payload.get("reason")
    if not field_name or not after_value or not reason:
        return jsonify({"error": "field_name, after_value, and reason are required"}), 400
    before_value = record.get(field_name)
    try:
        updated = update_record_field(record_id, field_name, after_value)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
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
            "INDIRECT" if record["status"] == "INDIRECT_PENDING" else "DEPT_HEAD",
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
    return jsonify({"record": updated})


@bp.post("/records/<int:record_id>/withdraw")
def withdraw(record_id: int):
    user, error = current_user_or_response()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    reason = payload.get("reason")
    if not reason:
        return jsonify({"error": "reason is required"}), 400
    record = get_record(record_id)
    if record is None:
        return jsonify({"error": "record not found"}), 404
    try:
        target_status = withdraw_status(record["status"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    updated = update_status(record_id, target_status)
    write_audit_log(
        action="WITHDRAW_RECORD",
        target_type="evaluation_record",
        target_id=record_id,
        operator_id=user["emp_id"],
        operator_name=user["username"],
        cycle_id=record["cycle_id"],
        before_snapshot={"status": record["status"]},
        after_snapshot={"status": target_status},
        reason=reason,
    )
    get_db().commit()
    return jsonify({"record": updated})
