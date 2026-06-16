from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.db import get_db
from performance_app.repositories.audit import write_audit_log
from performance_app.repositories.cycles import (
    create_cycle,
    delete_preparing_cycle,
    has_active_cycle,
    list_cycles,
    update_cycle_status,
)

bp = Blueprint("cycles", __name__)


def operator() -> tuple[str, str]:
    return (
        request.headers.get("X-Operator-Id", "system"),
        request.headers.get("X-Operator-Name", "系统"),
    )


@bp.get("/cycles")
def cycles_index():
    return jsonify({"cycles": list_cycles()})


@bp.post("/cycles")
def cycles_create():
    payload = request.get_json(silent=True) or {}
    cycle_name = payload.get("cycle_name")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")

    if not cycle_name or not start_date or not end_date:
        return jsonify({"error": "cycle_name, start_date, and end_date are required"}), 400

    operator_id, operator_name = operator()
    try:
        cycle = create_cycle(cycle_name, start_date, end_date, operator_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    write_audit_log(
        action="CREATE_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle["id"],
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle["id"],
        after_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"cycle": cycle}), 201


@bp.post("/cycles/<int:cycle_id>/start")
def cycles_start(cycle_id: int):
    if has_active_cycle(excluding_cycle_id=cycle_id):
        return jsonify({"error": "another ACTIVE cycle already exists"}), 409

    cycle = update_cycle_status(cycle_id, "PREPARING", "ACTIVE")
    if cycle is None:
        return jsonify({"error": "cycle is not PREPARING or does not exist"}), 409

    operator_id, operator_name = operator()
    write_audit_log(
        action="START_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"cycle": cycle})


@bp.post("/cycles/<int:cycle_id>/close")
def cycles_close(cycle_id: int):
    cycle = update_cycle_status(cycle_id, "ACTIVE", "CLOSED")
    if cycle is None:
        return jsonify({"error": "cycle is not ACTIVE or does not exist"}), 409

    operator_id, operator_name = operator()
    write_audit_log(
        action="CLOSE_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"cycle": cycle})


@bp.delete("/cycles/<int:cycle_id>")
def cycles_delete(cycle_id: int):
    cycle = delete_preparing_cycle(cycle_id)
    if cycle is None:
        return jsonify({"error": "only PREPARING cycles can be deleted"}), 409

    operator_id, operator_name = operator()
    write_audit_log(
        action="DELETE_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        before_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"deleted": True})
