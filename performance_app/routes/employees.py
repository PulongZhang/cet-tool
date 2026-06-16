from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from performance_app.repositories.employees import list_cycle_employees, list_import_errors
from performance_app.services.employee_import import import_employee_rows
from performance_app.services.excel_import import EMPLOYEE_HEADERS, build_template, parse_employee_workbook

bp = Blueprint("employees", __name__)


@bp.get("/cycles/<int:cycle_id>/employees")
def cycle_employees(cycle_id: int):
    return jsonify({"employees": list_cycle_employees(cycle_id)})


@bp.get("/cycles/<int:cycle_id>/employees/template")
def employee_template(cycle_id: int):
    return send_file(
        build_template(EMPLOYEE_HEADERS),
        as_attachment=True,
        download_name=f"cycle-{cycle_id}-employees-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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


@bp.post("/cycles/<int:cycle_id>/employees/upload")
def upload_employees(cycle_id: int):
    uploaded_file = request.files.get("file")
    if uploaded_file is None:
        return jsonify({"error": "file is required"}), 400
    try:
        rows = parse_employee_workbook(uploaded_file)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    operator_id = request.headers.get("X-Operator-Id", "system")
    result = import_employee_rows(cycle_id, uploaded_file.filename or "employees.xlsx", rows, operator_id)
    return jsonify(result)
