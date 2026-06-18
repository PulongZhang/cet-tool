from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from performance_app.repositories.employees import list_cycle_employees, list_cycle_accounts, list_import_errors
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


ACCOUNT_EXPORT_HEADERS = ["工号", "姓名", "部门", "序列", "职级", "登录账号", "账号状态", "角色", "直接上级", "间接上级", "部门负责人", "初始密码"]


@bp.get("/cycles/<int:cycle_id>/accounts/export")
def export_cycle_accounts(cycle_id: int):
    """导出周期内员工账号清单Excel"""
    from openpyxl import Workbook

    accounts = list_cycle_accounts(cycle_id)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "员工账号清单"

    # 表头
    sheet.append(ACCOUNT_EXPORT_HEADERS)

    # 数据行
    DEFAULT_PASSWORD = "ChangeMe123!"
    for acc in accounts:
        sheet.append([
            acc["emp_id"],
            acc["emp_name"],
            acc.get("dept_level_1") or acc["dept_name"] or "-",
            acc["sequence"] or "-",
            acc["level"] or "-",
            acc["username"] or "-",
            acc["status"] or "-",
            acc["roles"] or "-",
            acc["direct_manager_id"] or "-",
            acc["indirect_manager_id"] or "-",
            acc["dept_head_id"] or "-",
            DEFAULT_PASSWORD if acc["username"] else "-",  # 初始密码固定显示
        ])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"cycle-{cycle_id}-accounts.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
