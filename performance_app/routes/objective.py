from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from performance_app.services.excel_import import OBJECTIVE_HEADERS, build_template, parse_objective_workbook
from performance_app.services.objective_import import correct_objective_data, import_objective_rows

bp = Blueprint("objective", __name__)


@bp.get("/objective/template")
def objective_template():
    return send_file(
        build_template(OBJECTIVE_HEADERS),
        as_attachment=True,
        download_name="objective-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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


@bp.post("/objective/upload")
def upload_objective_data():
    cycle_id = request.form.get("cycle_id", type=int)
    if not cycle_id:
        return jsonify({"error": "cycle_id is required"}), 400
    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        return jsonify({"error": "file is required"}), 400
    try:
        rows = parse_objective_workbook(uploaded_file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    result = import_objective_rows(cycle_id, uploaded_file.filename or "objective.xlsx", rows, operator_id, operator_name)
    return jsonify(result)


@bp.post("/objective/<int:objective_id>/correct")
def correct_objective(objective_id: int):
    payload = request.get_json(silent=True) or {}
    reason = payload.get("reason")
    level_updates = {
        field: payload.get(field)
        for field in ("diligence_level", "discipline_level", "learning_level")
        if payload.get(field)
    }
    if not reason or not level_updates:
        return jsonify({"error": "reason and at least one objective level are required"}), 400

    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    try:
        objective = correct_objective_data(objective_id, level_updates, reason, operator_id, operator_name)
    except LookupError:
        return jsonify({"error": "objective data not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"objective": objective})
