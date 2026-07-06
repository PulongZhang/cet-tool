from __future__ import annotations

from pathlib import Path

from flask import current_app
from openpyxl import Workbook

from performance_app.db import get_db
from performance_app.repositories.audit import write_audit_log
from performance_app.services.calculation_runner import list_cycle_results
from performance_app.routes.pages import STATUS_LABELS

RESULT_HEADERS = ("工号", "姓名", "四级部门", "职级", "加权分", "排序", "部门负责人初评结果", "加权计算结果", "最终微调结果", "状态")


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
                record.get("dept_level_4") or record.get("dept_name") or "-",
                record.get("level") or "-",
                record.get("weighted_score") or "-",
                record.get("rank_in_group") or "-",
                record.get("current_subjective_level") or "-",
                record.get("suggested_level") or "-",
                record.get("final_level") or "-",
                STATUS_LABELS.get(record.get("status"), record.get("status") or "-"),
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


PROCESS_HEADERS = ("工号", "姓名", "四级部门", "职级",
                   "勤奋总量", "勤奋月均", "勤奋等级",
                   "纪律异常次数", "纪律等级",
                   "学习时长(h)", "学习排名%", "学习等级",
                   "部门负责人评价")

PROCESS_QUERY = """
    select
        s.emp_id, s.emp_name, s.dept_level_4, s.dept_name, s.level,
        o.diligence_raw_total, o.diligence_month_avg, o.diligence_level,
        o.discipline_raw_count, o.discipline_level,
        o.learning_hours, o.learning_rank_pct, o.learning_level,
        r.current_subjective_level
    from cycle_employee_snapshot s
    left join objective_data o on o.cycle_id = s.cycle_id and o.emp_id = s.emp_id
    left join evaluation_record r on r.cycle_id = s.cycle_id and r.emp_id = s.emp_id
    where s.cycle_id = ? and s.active = 1
    order by s.emp_id
"""


def create_process_export(cycle_id: int, operator_id: str, operator_name: str) -> dict:
    """导出过程计算数据:每个人的三项客观数据(原始值+等级) + 部门负责人确认等级。"""
    rows = get_db().execute(PROCESS_QUERY, (cycle_id,)).fetchall()
    if not rows:
        raise ValueError("no employees to export")

    export_id = f"cycle-{cycle_id}-process"
    export_dir = Path(current_app.config["EXPORT_DIR"]).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    file_path = export_dir / f"{export_id}.xlsx"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "过程计算数据"
    sheet.append(PROCESS_HEADERS)
    for row in rows:
        sheet.append((
            row["emp_id"],
            row["emp_name"],
            row["dept_level_4"] or row["dept_name"] or "-",
            row["level"] or "-",
            row["diligence_raw_total"] if row["diligence_raw_total"] is not None else "-",
            row["diligence_month_avg"] if row["diligence_month_avg"] is not None else "-",
            row["diligence_level"] or "-",
            row["discipline_raw_count"] if row["discipline_raw_count"] is not None else "-",
            row["discipline_level"] or "-",
            row["learning_hours"] if row["learning_hours"] is not None else "-",
            row["learning_rank_pct"] if row["learning_rank_pct"] is not None else "-",
            row["learning_level"] or "-",
            row["current_subjective_level"] or "-",
        ))
    workbook.save(file_path)

    write_audit_log(
        action="EXPORT_EXCEL",
        target_type="export_file",
        target_id=export_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot={"export_id": export_id, "export_type": "process", "file_name": file_path.name},
    )
    get_db().commit()
    return {"export_id": export_id, "file_name": file_path.name, "download_url": f"/exports/{export_id}/download"}


def export_file_path(export_id: str) -> Path:
    return Path(current_app.config["EXPORT_DIR"]).resolve() / f"{export_id}.xlsx"
