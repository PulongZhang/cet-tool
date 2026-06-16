from __future__ import annotations

from pathlib import Path

from flask import current_app
from openpyxl import Workbook

from performance_app.db import get_db
from performance_app.repositories.audit import write_audit_log
from performance_app.services.calculation_runner import list_cycle_results

RESULT_HEADERS = ("工号", "姓名", "部门", "分组", "加权分", "组内排名", "组内人数", "系统建议等级", "最终等级")


def create_cycle_export(cycle_id: int, export_type: str, operator_id: str, operator_name: str) -> dict:
    records = list_cycle_results(cycle_id)
    if not records:
        raise ValueError("no calculated results to export")

    export_id = f"cycle-{cycle_id}-{export_type}"
    export_dir = Path(current_app.config["EXPORT_DIR"]).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    file_path = export_dir / f"{export_id}.xlsx"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "结果总览"
    sheet.append(RESULT_HEADERS)
    for record in records:
        sheet.append(
            (
                record["emp_id"],
                record["emp_name"],
                record["dept_name"],
                record["group_code"],
                record["weighted_score"],
                record["rank_in_group"],
                record["rank_total"],
                record["suggested_level"],
                record["final_level"],
            )
        )
    workbook.save(file_path)

    write_audit_log(
        action="EXPORT_EXCEL",
        target_type="export_file",
        target_id=export_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot={"export_id": export_id, "export_type": export_type, "file_name": file_path.name},
    )
    get_db().commit()
    return {"export_id": export_id, "file_name": file_path.name, "download_url": f"/exports/{export_id}/download"}


def export_file_path(export_id: str) -> Path:
    return Path(current_app.config["EXPORT_DIR"]).resolve() / f"{export_id}.xlsx"
