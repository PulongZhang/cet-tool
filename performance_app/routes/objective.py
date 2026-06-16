from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.services.objective_import import import_objective_rows

bp = Blueprint("objective", __name__)


@bp.post("/objective/import")
def import_objective_data():
    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    rows = payload.get("rows")
    if not cycle_id:
        return jsonify({"error": "cycle_id is required"}), 400
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list"}), 400

    file_name = payload.get("file_name") or "objective.json"
    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    result = import_objective_rows(int(cycle_id), file_name, rows, operator_id, operator_name)
    return jsonify(result)
