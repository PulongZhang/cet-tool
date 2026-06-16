from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.services.calculation_runner import (
    CalculationPrerequisiteError,
    adjust_final_level,
    calculate_cycle,
    calculation_detail,
    finalize_cycle_results,
    list_cycle_results,
)

bp = Blueprint("results", __name__)


@bp.post("/cycles/<int:cycle_id>/calculate")
def calculate_results(cycle_id: int):
    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    try:
        result = calculate_cycle(cycle_id, operator_id, operator_name)
    except CalculationPrerequisiteError as exc:
        return jsonify({"error": str(exc), "missing": exc.missing}), 409
    return jsonify(result)


@bp.get("/cycles/<int:cycle_id>/results")
def cycle_results(cycle_id: int):
    return jsonify({"records": list_cycle_results(cycle_id)})


@bp.post("/cycles/<int:cycle_id>/results/finalize")
def finalize_results(cycle_id: int):
    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    updated_count = finalize_cycle_results(cycle_id, operator_id, operator_name)
    return jsonify({"updated_count": updated_count})


@bp.get("/records/<int:record_id>/calculation-detail")
def record_calculation_detail(record_id: int):
    try:
        detail = calculation_detail(record_id)
    except CalculationPrerequisiteError as exc:
        return jsonify({"error": str(exc), "missing": exc.missing}), 409
    if detail is None:
        return jsonify({"error": "record not found"}), 404
    return jsonify({"detail": detail})


@bp.post("/records/<int:record_id>/final-level")
def update_final_level(record_id: int):
    payload = request.get_json(silent=True) or {}
    final_level = payload.get("final_level")
    reason = payload.get("reason")
    if not final_level or not reason:
        return jsonify({"error": "final_level and reason are required"}), 400

    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    try:
        record = adjust_final_level(record_id, final_level, reason, operator_id, operator_name)
    except LookupError:
        return jsonify({"error": "record not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"record": record})
