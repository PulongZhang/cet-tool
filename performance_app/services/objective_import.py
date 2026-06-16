from __future__ import annotations

from performance_app.db import get_db
from performance_app.domain.objectives import (
    diligence_level_from_quarter_total,
    discipline_level_from_exception_count,
    learning_level_from_rank_pct,
)
from performance_app.repositories.audit import write_audit_log
from performance_app.repositories.employees import add_import_error, create_import_batch, update_import_batch_counts

MONTH_FIELDS = ("diligence_month_1", "diligence_month_2", "diligence_month_3")
COUNT_FIELDS = ("attendance_exception_count", "log_exception_count")
REQUIRED_FIELDS = ("emp_id", *MONTH_FIELDS, *COUNT_FIELDS, "learning_hours")


def import_objective_rows(cycle_id: int, file_name: str, rows: list[dict], operator_id: str, operator_name: str) -> dict:
    batch_id = create_import_batch(cycle_id, "OBJECTIVE_DATA", file_name, len(rows), operator_id)
    seen_emp_ids: set[str] = set()
    valid_rows: list[dict] = []
    errors: list[dict] = []

    for index, row in enumerate(rows, start=2):
        normalized, error = validate_row(cycle_id, row, index, seen_emp_ids)
        if error:
            errors.append(error)
            add_import_error(batch_id, error, row)
            continue
        valid_rows.append(normalized)

    apply_learning_ranks(valid_rows)
    for row in valid_rows:
        upsert_objective_data(cycle_id, row)

    update_import_batch_counts(batch_id, len(valid_rows), len(errors))
    write_audit_log(
        action="IMPORT_OBJECTIVE_DATA",
        target_type="import_batch",
        target_id=batch_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot={"summary": {"total_count": len(rows), "success_count": len(valid_rows), "failed_count": len(errors)}},
    )
    get_db().commit()

    return {
        "batch_id": batch_id,
        "summary": {
            "total_count": len(rows),
            "success_count": len(valid_rows),
            "failed_count": len(errors),
        },
        "errors": errors,
    }


def validate_row(cycle_id: int, row: dict, row_number: int, seen_emp_ids: set[str]) -> tuple[dict | None, dict | None]:
    for field in REQUIRED_FIELDS:
        if row.get(field) in (None, ""):
            return None, row_error(row_number, row.get("emp_id"), field, f"{field} is required")

    emp_id = str(row["emp_id"]).strip()
    if emp_id in seen_emp_ids:
        return None, row_error(row_number, emp_id, "emp_id", "duplicate emp_id in import file")

    group_code = group_code_for_emp(cycle_id, emp_id)
    if group_code is None:
        return None, row_error(row_number, emp_id, "emp_id", "emp_id does not exist in cycle")

    numeric_values: dict[str, float] = {}
    for field in (*MONTH_FIELDS, "learning_hours"):
        value, error = parse_non_negative_float(row[field], field, row_number, emp_id)
        if error:
            return None, error
        numeric_values[field] = value

    count_values: dict[str, int] = {}
    for field in COUNT_FIELDS:
        value, error = parse_non_negative_int(row[field], field, row_number, emp_id)
        if error:
            return None, error
        count_values[field] = value

    seen_emp_ids.add(emp_id)
    diligence_raw_total = sum(numeric_values[field] for field in MONTH_FIELDS)
    discipline_raw_count = sum(count_values[field] for field in COUNT_FIELDS)
    return {
        "emp_id": emp_id,
        "group_code": group_code,
        "diligence_raw_total": diligence_raw_total,
        "diligence_month_avg": round(diligence_raw_total / 3, 1),
        "diligence_level": diligence_level_from_quarter_total(diligence_raw_total),
        "discipline_raw_count": discipline_raw_count,
        "discipline_level": discipline_level_from_exception_count(discipline_raw_count),
        "learning_hours": numeric_values["learning_hours"],
    }, None


def group_code_for_emp(cycle_id: int, emp_id: str) -> str | None:
    row = get_db().execute(
        "select group_code from cycle_employee_snapshot where cycle_id = ? and emp_id = ?",
        (cycle_id, emp_id),
    ).fetchone()
    return row["group_code"] if row else None


def parse_non_negative_float(value: object, field: str, row_number: int, emp_id: str) -> tuple[float | None, dict | None]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None, row_error(row_number, emp_id, field, f"{field} must be numeric")
    if parsed < 0:
        return None, row_error(row_number, emp_id, field, f"{field} cannot be negative")
    return parsed, None


def parse_non_negative_int(value: object, field: str, row_number: int, emp_id: str) -> tuple[int | None, dict | None]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, row_error(row_number, emp_id, field, f"{field} must be an integer")
    if parsed < 0:
        return None, row_error(row_number, emp_id, field, f"{field} cannot be negative")
    return parsed, None


def apply_learning_ranks(rows: list[dict]) -> None:
    rows_by_group: dict[str, list[dict]] = {}
    for row in rows:
        rows_by_group.setdefault(row["group_code"], []).append(row)

    for group_rows in rows_by_group.values():
        ranked = sorted(group_rows, key=lambda row: (-row["learning_hours"], row["emp_id"]))
        total = len(ranked)
        for index, row in enumerate(ranked, start=1):
            rank_pct = round(index / total * 100, 1)
            row["learning_rank_pct"] = rank_pct
            row["learning_level"] = learning_level_from_rank_pct(rank_pct)


def upsert_objective_data(cycle_id: int, row: dict) -> None:
    get_db().execute(
        """
        insert into objective_data
            (cycle_id, emp_id, diligence_raw_total, diligence_month_avg, diligence_level,
             discipline_raw_count, discipline_level, learning_hours, learning_rank_pct, learning_level,
             corrected, correction_reason, updated_at)
        values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, null, datetime('now'))
        on conflict(cycle_id, emp_id) do update set
            diligence_raw_total = excluded.diligence_raw_total,
            diligence_month_avg = excluded.diligence_month_avg,
            diligence_level = excluded.diligence_level,
            discipline_raw_count = excluded.discipline_raw_count,
            discipline_level = excluded.discipline_level,
            learning_hours = excluded.learning_hours,
            learning_rank_pct = excluded.learning_rank_pct,
            learning_level = excluded.learning_level,
            corrected = 0,
            correction_reason = null,
            updated_at = datetime('now')
        """,
        (
            cycle_id,
            row["emp_id"],
            row["diligence_raw_total"],
            row["diligence_month_avg"],
            row["diligence_level"],
            row["discipline_raw_count"],
            row["discipline_level"],
            row["learning_hours"],
            row["learning_rank_pct"],
            row["learning_level"],
        ),
    )


def row_error(row_number: int, emp_id: str | None, field_name: str, error_message: str) -> dict:
    return {
        "row_number": row_number,
        "emp_id": emp_id,
        "field_name": field_name,
        "error_message": error_message,
    }
