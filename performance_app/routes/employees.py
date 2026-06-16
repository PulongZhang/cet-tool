from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.repositories.employees import list_cycle_employees, list_import_errors
from performance_app.services.employee_import import import_employee_rows

bp = Blueprint("employees", __name__)


@bp.get("/cycles/<int:cycle_id>/employees")
def cycle_employees(cycle_id: int):
    return jsonify({"employees": list_cycle_employees(cycle_id)})


@bp.get("/imports/<int:batch_id>/errors")
def import_errors(batch_id: int):
    return jsonify({"errors": list_import_errors(batch_id)})


@bp.post("/cycles/<int:cycle_id>/employees/import")
def import_employees(cycle_id: int):
    payload = request.get_json(silent=True) or {}
    file_name = payload.get("file_name") or "employees.json"
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list"}), 400

    operator_id = request.headers.get("X-Operator-Id", "system")
    result = import_employee_rows(cycle_id, file_name, rows, operator_id)
    return jsonify(result)
