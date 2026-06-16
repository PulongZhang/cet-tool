from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from performance_app.services.export_files import create_cycle_export, export_file_path

bp = Blueprint("exports", __name__)


@bp.post("/cycles/<int:cycle_id>/exports/initial")
def export_initial_results(cycle_id: int):
    return export_results(cycle_id, "initial")


@bp.post("/cycles/<int:cycle_id>/exports/final")
def export_final_results(cycle_id: int):
    return export_results(cycle_id, "final")


def export_results(cycle_id: int, export_type: str):
    operator_id = request.headers.get("X-Operator-Id", "system")
    operator_name = request.headers.get("X-Operator-Name", operator_id)
    try:
        export = create_cycle_export(cycle_id, export_type, operator_id, operator_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"export": export})


@bp.get("/exports/<export_id>/download")
def download_export(export_id: str):
    file_path = export_file_path(export_id)
    if not file_path.exists():
        return jsonify({"error": "export not found"}), 404
    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_path.name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
