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
    "direct_manager_id",
    "indirect_manager_id",
    "dept_head_id",
]

OPTIONAL_FIELDS = [
    "dept_level_1",
    "dept_level_2",
    "dept_level_3",
    "dept_level_4",
    "post",
    "roles",
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
    for field in OPTIONAL_FIELDS:
        value = row.get(field)
        normalized[field] = value.strip() if value else ""

    try:
        group_code = derive_group_code(normalized["sequence"], normalized["level"])
    except ValueError as exc:
        return None, {
            "row_number": row_number,
            "emp_id": emp_id,
            "field_name": "level",
            "error_message": str(exc),
        }

    # 组合部门名称：使用一级部门作为主要部门名称
    normalized["dept_name"] = normalized["dept_level_1"] or normalized.get("dept_level_2") or normalized.get("dept_level_3") or "未知部门"

    seen_emp_ids.add(emp_id)
    normalized["group_code"] = group_code
    return normalized, None


def role_map_for_rows(rows: list[dict]) -> dict[str, set[str]]:
    imported_ids = {row["emp_id"] for row in rows}
    roles = {emp_id: set() for emp_id in imported_ids}

    for row in rows:
        emp_id = row["emp_id"]

        # 如果Excel中指定了角色，使用指定的角色
        if row.get("roles"):
            specified_roles = str(row["roles"]).strip()
            # 支持多种分隔符：逗号、分号、空格、斜杠
            for sep in [",", ";", " ", "/", "|", "\n"]:
                if sep in specified_roles:
                    role_list = [r.strip() for r in specified_roles.split(sep) if r.strip()]
                    roles[emp_id] = set(role_list)
                    break
            else:
                # 没有分隔符，作为单个角色
                if specified_roles:
                    roles[emp_id] = {specified_roles}
        else:
            # 没有指定角色，默认为员工
            roles[emp_id] = {"EMPLOYEE"}

        # 无论Excel中是否指定角色，都根据组织关系推断管理角色
        # 这样可以确保既有的管理功能正常工作
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

    if errors:
        update_import_batch_counts(batch_id, 0, len(errors))
        get_db().commit()
        return {
            "batch_id": batch_id,
            "summary": {
                "total_count": len(rows),
                "success_count": 0,
                "failed_count": len(errors),
            },
            "errors": errors,
        }

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

    update_import_batch_counts(batch_id, len(valid_rows), 0)
    get_db().commit()

    return {
        "batch_id": batch_id,
        "summary": {
            "total_count": len(rows),
            "success_count": len(valid_rows),
            "failed_count": 0,
        },
        "errors": [],
    }
