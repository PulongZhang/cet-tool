from __future__ import annotations

from performance_app.db import get_db
from performance_app.domain.employees import derive_group_code
from performance_app.repositories.accounts import ensure_account
from performance_app.repositories.employees import (
    add_import_error,
    create_import_batch,
    ensure_evaluation_record,
    update_import_batch_counts,
    upsert_snapshot,
)

REQUIRED_FIELDS = [
    "emp_id",
    "emp_name",
    "sequence",
    "level",
    "dept_name",
    "direct_manager_id",
    "indirect_manager_id",
    "dept_head_id",
]
DEFAULT_PASSWORD = "ChangeMe123!"


def validate_row(row: dict, row_number: int, seen_emp_ids: set[str]) -> tuple[dict | None, dict | None]:
    for field in REQUIRED_FIELDS:
        if not row.get(field):
            return None, {
                "row_number": row_number,
                "emp_id": row.get("emp_id"),
                "field_name": field,
                "error_message": f"{field} is required",
            }

    emp_id = row["emp_id"].strip()
    if emp_id in seen_emp_ids:
        return None, {
            "row_number": row_number,
            "emp_id": emp_id,
            "field_name": "emp_id",
            "error_message": "duplicate emp_id in import file",
        }

    normalized = {field: str(row[field]).strip() for field in REQUIRED_FIELDS}
    try:
        group_code = derive_group_code(normalized["sequence"], normalized["level"])
    except ValueError as exc:
        return None, {
            "row_number": row_number,
            "emp_id": emp_id,
            "field_name": "level",
            "error_message": str(exc),
        }

    seen_emp_ids.add(emp_id)
    normalized["group_code"] = group_code
    return normalized, None


def role_map_for_rows(rows: list[dict]) -> dict[str, set[str]]:
    imported_ids = {row["emp_id"] for row in rows}
    roles = {emp_id: {"EMPLOYEE"} for emp_id in imported_ids}

    for row in rows:
        if row["direct_manager_id"] in imported_ids:
            roles[row["direct_manager_id"]].add("DIRECT_MANAGER")
        if row["indirect_manager_id"] in imported_ids:
            roles[row["indirect_manager_id"]].add("INDIRECT_MANAGER")
        if row["dept_head_id"] in imported_ids:
            roles[row["dept_head_id"]].add("DEPT_HEAD")

    return roles


def import_employee_rows(cycle_id: int, file_name: str, rows: list[dict], operator_id: str) -> dict:
    batch_id = create_import_batch(cycle_id, "EMPLOYEE", file_name, len(rows), operator_id)
    seen_emp_ids: set[str] = set()
    valid_rows: list[dict] = []
    errors: list[dict] = []

    for index, row in enumerate(rows, start=2):
        normalized, error = validate_row(row, index, seen_emp_ids)
        if error:
            errors.append(error)
            add_import_error(batch_id, error, row)
            continue
        valid_rows.append(normalized)

    roles_by_emp_id = role_map_for_rows(valid_rows)
    for row in valid_rows:
        upsert_snapshot(cycle_id, row, row["group_code"])
        ensure_evaluation_record(cycle_id, row["emp_id"])
        ensure_account(
            row["emp_id"],
            row["emp_id"],
            DEFAULT_PASSWORD,
            sorted(roles_by_emp_id[row["emp_id"]]),
        )

    update_import_batch_counts(batch_id, len(valid_rows), len(errors))
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
