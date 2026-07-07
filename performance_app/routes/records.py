from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.db import get_db
from performance_app.repositories.accounts import find_by_id
from performance_app.repositories.records import (
    get_my_record,
    get_record,
    list_direct_reports,
    submit_direct_report_drafts,
    update_manager_score,
    update_self_review,
)

bp = Blueprint("records", __name__)

COMMENT_REQUIRED_GRADES = {"A+", "A", "C", "D"}
SELF_EDITABLE_STATUSES = {"SELF_PENDING", "SELF_DRAFT"}

CYCLE_ID_REQUIRED = "cycle_id is required"
RECORD_NOT_FOUND = "record not found"


def current_user_or_response():
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return None, (jsonify({"error": "X-User-Id header is required"}), 401)
    try:
        user = find_by_id(int(user_id))
    except ValueError:
        return None, (jsonify({"error": "X-User-Id header must be an integer"}), 400)
    if user is None:
        return None, (jsonify({"error": "user not found"}), 404)
    return user, None


def require_fields(payload: dict, fields: list[str]):
    missing = [field for field in fields if not payload.get(field)]
    if missing:
        return jsonify({"error": f"missing required fields: {', '.join(missing)}"}), 400
    return None


@bp.get("/records/my")
def my_record():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = request.args.get("cycle_id", type=int)
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    record = get_my_record(cycle_id, user["emp_id"])
    if record is None:
        return jsonify({"error": RECORD_NOT_FOUND}), 404
    return jsonify({"record": record})


@bp.post("/records/<int:record_id>/self-draft")
def self_draft(record_id: int):
    user, error = current_user_or_response()
    if error:
        return error
    record = get_record(record_id)
    if record is None:
        return jsonify({"error": RECORD_NOT_FOUND}), 404
    if record["emp_id"] != user["emp_id"]:
        return jsonify({"error": "forbidden"}), 403
    if record["status"] not in SELF_EDITABLE_STATUSES:
        return jsonify({"error": "self review is locked"}), 409
    payload = request.get_json(silent=True) or {}
    field_error = require_fields(payload, ["self_score_1", "self_score_2", "self_score_3"])
    if field_error:
        return field_error
    updated = update_self_review(record_id, payload, "SELF_DRAFT")
    get_db().commit()
    return jsonify({"record": updated})


@bp.post("/records/<int:record_id>/self-submit")
def self_submit(record_id: int):
    user, error = current_user_or_response()
    if error:
        return error
    record = get_record(record_id)
    if record is None:
        return jsonify({"error": RECORD_NOT_FOUND}), 404
    if record["emp_id"] != user["emp_id"]:
        return jsonify({"error": "forbidden"}), 403
    if record["status"] not in SELF_EDITABLE_STATUSES:
        return jsonify({"error": "self review is locked"}), 409
    payload = request.get_json(silent=True) or {}
    field_error = require_fields(payload, ["self_score_1", "self_score_2", "self_score_3"])
    if field_error:
        return field_error
    updated = update_self_review(record_id, payload, "DIRECT_PENDING")
    get_db().commit()
    return jsonify({"record": updated})


@bp.get("/records/direct-reports")
def direct_reports():
    user, error = current_user_or_response()
    if error:
        return error
    cycle_id = request.args.get("cycle_id", type=int)
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    return jsonify({"records": list_direct_reports(cycle_id, user["emp_id"])})


def blocking_records(records: list[dict], expected_status: str) -> list[dict]:
    return [
        {"record_id": record["id"], "emp_id": record["emp_id"], "status": record["status"]}
        for record in records
        if record["status"] != expected_status
    ]


@bp.post("/records/<int:record_id>/manager-draft")
def manager_draft(record_id: int):
    return save_manager(record_id, "DIRECT_DRAFT")


@bp.post("/records/direct-reports/submit")
def submit_direct_reports():
    user, error = current_user_or_response()
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    if not cycle_id:
        return jsonify({"error": CYCLE_ID_REQUIRED}), 400
    reports = list_direct_reports(int(cycle_id), user["emp_id"])
    blocking = blocking_records(reports, "DIRECT_DRAFT")
    if blocking:
        return jsonify({"error": "not all direct reports are ready to submit", "blocking_records": blocking}), 409
    updated = submit_direct_report_drafts(int(cycle_id), user["emp_id"])
    get_db().commit()
    return jsonify({"updated_count": updated})


@bp.post("/records/<int:record_id>/manager-submit")
def manager_submit(record_id: int):
    return save_manager(record_id, "INDIRECT_PENDING")


def save_manager(record_id: int, status: str):
    user, error = current_user_or_response()
    if error:
        return error
    record = get_record(record_id)
    if record is None:
        return jsonify({"error": RECORD_NOT_FOUND}), 404
    if record["direct_manager_id"] != user["emp_id"]:
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    field_error = require_fields(payload, ["manager_score_1", "manager_score_2", "manager_score_3", "initial_total_grade"])
    if field_error:
        return field_error
    if payload.get("initial_total_grade") in COMMENT_REQUIRED_GRADES and not payload.get("manager_comment"):
        return jsonify({"error": "manager_comment is required for A+, A, C, or D"}), 400
    updated = update_manager_score(record_id, payload, status)
    get_db().commit()
    return jsonify({"record": updated})
