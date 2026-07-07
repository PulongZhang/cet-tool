from __future__ import annotations

from pathlib import Path

from flask import current_app

from performance_app.db import get_db
from performance_app.domain.employees import derive_group_code
from performance_app.repositories.accounts import ensure_account, generate_random_password
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
]

MANAGER_FIELDS = [
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
# 系统允许的角色列表
VALID_ROLES = {"EMPLOYEE", "DIRECT_MANAGER", "INDIRECT_MANAGER", "DEPT_HEAD", "HRBP", "ADMIN"}

# 经理字段 -> 中文标签(自检与导入解析共用)
MANAGER_FIELD_LABELS = {
    "direct_manager_id": "直接上级",
    "indirect_manager_id": "间接上级",
    "dept_head_id": "部门负责人",
}

# 角色字段支持的分隔符
ROLE_SEPARATORS = [",", ";", " ", "/", "|", "\n"]


def _split_roles(raw: str) -> list[str]:
    """按多种分隔符拆分角色文本;无分隔符时视为单个角色。"""
    for sep in ROLE_SEPARATORS:
        if sep in raw:
            return [part.strip() for part in raw.split(sep) if part.strip()]
    return [raw] if raw else []


def _manager_self_violation(normalized: dict, emp_id: str) -> tuple[str, str] | None:
    """若某经理字段等于员工自己工号,返回 (field, label),否则 None。"""
    for field, label in MANAGER_FIELD_LABELS.items():
        if normalized.get(field) and normalized[field] == emp_id:
            return field, label
    return None


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
    # 经理字段可选，允许最高级管理者不填写上级
    for field in (*MANAGER_FIELDS, *OPTIONAL_FIELDS):
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

    # 验证角色值
    roles_value = normalized.get("roles", "")
    if roles_value:
        invalid_roles = [r for r in _split_roles(roles_value) if r not in VALID_ROLES]
        if invalid_roles:
            return None, {
                "row_number": row_number,
                "emp_id": emp_id,
                "field_name": "roles",
                "error_message": f"Invalid role(s): {', '.join(invalid_roles)}. Valid roles are: {', '.join(sorted(VALID_ROLES))}",
            }

    # 验证经理字段不能是自己的工号（如果填写了的话）
    violation = _manager_self_violation(normalized, emp_id)
    if violation:
        field, label = violation
        return None, {
            "row_number": row_number,
            "emp_id": emp_id,
            "field_name": field,
            "error_message": f"{label}不能是员工自己的工号",
        }

    seen_emp_ids.add(emp_id)
    normalized["group_code"] = group_code
    return normalized, None


# 组织关系字段 -> 自动推断的管理角色
MANAGER_ROLE_BY_FIELD = {
    "direct_manager_id": "DIRECT_MANAGER",
    "indirect_manager_id": "INDIRECT_MANAGER",
    "dept_head_id": "DEPT_HEAD",
}


def role_map_for_rows(rows: list[dict]) -> dict[str, set[str]]:
    imported_ids = {row["emp_id"] for row in rows}
    roles = {emp_id: set() for emp_id in imported_ids}
    # 第一遍：先标记哪些员工在Excel中明确指定了角色
    specified_in_excel: set[str] = set()

    for row in rows:
        emp_id = row["emp_id"]
        spec = row.get("roles")
        if spec:
            # 如果Excel中指定了角色，使用指定的角色
            roles[emp_id] = set(_split_roles(str(spec).strip()))
            specified_in_excel.add(emp_id)
        else:
            # 没有指定角色，默认为员工
            roles[emp_id] = {"EMPLOYEE"}

    # 第二遍：只有当Excel中未明确指定角色时，才根据组织关系推断管理角色
    for row in rows:
        for field, role in MANAGER_ROLE_BY_FIELD.items():
            manager_id = row.get(field)
            if manager_id and manager_id in imported_ids and manager_id not in specified_in_excel:
                roles[manager_id].add(role)

    return roles


def _write_password_xlsx(new_accounts: list[dict], batch_id: int) -> str:
    """把本次新建账号的明文密码写入 xlsx(账号清单格式),返回文件名。"""
    from openpyxl import Workbook

    export_dir = Path(current_app.config["EXPORT_DIR"]).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"account_passwords_{batch_id}.xlsx"
    file_path = export_dir / file_name
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "新增账号密码"
    sheet.append(["工号", "姓名", "部门", "角色", "登录账号", "初始密码"])
    for acc in new_accounts:
        sheet.append([
            acc["emp_id"],
            acc["emp_name"],
            acc.get("dept_name") or "-",
            acc.get("roles") or "-",
            acc["username"],
            acc["password"],
        ])
    workbook.save(file_path)
    return file_name


def _collect_name_id_maps(rows: list[dict]) -> tuple[dict[str, str], set[str]]:
    """建立 姓名->工号 映射(重名取首个)与全部工号集合。"""
    name_to_emp_id: dict[str, str] = {}
    emp_id_set: set[str] = set()
    for row in rows:
        emp_id = (row.get("emp_id") or "").strip()
        emp_name = (row.get("emp_name") or "").strip()
        if emp_id and emp_name:
            emp_id_set.add(emp_id)
            if emp_name not in name_to_emp_id:
                name_to_emp_id[emp_name] = emp_id
    return name_to_emp_id, emp_id_set


def _resolve_manager_value(value, emp_id_set: set[str], name_to_emp_id: dict[str, str]) -> str | None:
    """工号直接用、姓名转工号;空值返回空串,无法识别返回 None。"""
    value = (value or "").strip()
    if not value:
        return ""
    if value in emp_id_set:
        return value
    if value in name_to_emp_id:
        return name_to_emp_id[value]
    return None


def _process_row_managers(row: dict, emp_id_set: set[str], name_to_emp_id: dict[str, str], index: int, batch_id: int, errors: list[dict]) -> tuple[dict, bool]:
    """转换一行的经理字段(姓名->工号)。返回 (处理后的行, 是否有错误)。"""
    processed_row = dict(row)
    has_error = False
    for field, label in MANAGER_FIELD_LABELS.items():
        raw = (row.get(field) or "").strip()
        if not raw:
            continue
        resolved = _resolve_manager_value(raw, emp_id_set, name_to_emp_id)
        if resolved is None:
            has_error = True
            errors.append({
                "row_number": index,
                "emp_id": row.get("emp_id"),
                "field_name": field,
                "error_message": f"{label}'{raw}'不是有效的工号或姓名（未在本次导入中找到）",
            })
            add_import_error(batch_id, errors[-1], row)
        else:
            processed_row[field] = resolved
    return processed_row, has_error


def import_employee_rows(cycle_id: int, file_name: str, rows: list[dict], operator_id: str) -> dict:
    batch_id = create_import_batch(cycle_id, "EMPLOYEE", file_name, len(rows), operator_id)

    # 第一阶段：收集所有员工数据，建立姓名->工号映射
    name_to_emp_id, emp_id_set = _collect_name_id_maps(rows)

    # 第二阶段：验证和转换
    seen_emp_ids: set[str] = set()
    valid_rows: list[dict] = []
    errors: list[dict] = []

    for index, row in enumerate(rows, start=2):
        # 先转换经理字段：如果是姓名，转换为工号
        processed_row, has_manager_error = _process_row_managers(row, emp_id_set, name_to_emp_id, index, batch_id, errors)
        if has_manager_error:
            continue

        # 经理字段都处理完了，继续验证整行
        normalized, error = validate_row(processed_row, index, seen_emp_ids)
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

    # 删除该周期所有旧员工数据，以最新上传的清单为准
    get_db().execute(
        "DELETE FROM evaluation_record WHERE cycle_id = ?",
        (cycle_id,),
    )
    get_db().execute(
        "DELETE FROM objective_data WHERE cycle_id = ?",
        (cycle_id,),
    )
    get_db().execute(
        "DELETE FROM cycle_employee_snapshot WHERE cycle_id = ?",
        (cycle_id,),
    )

    roles_by_emp_id = role_map_for_rows(valid_rows)
    new_accounts: list[dict] = []
    for row in valid_rows:
        upsert_snapshot(cycle_id, row, row["group_code"])
        # 所有人都需要创建 evaluation_record（走完整评分流程）
        # EXCLUDED 人员在最终计算排序时会被排除
        ensure_evaluation_record(cycle_id, row["emp_id"])
        password = generate_random_password()
        _user, created = ensure_account(
            row["emp_id"],
            row["emp_id"],
            password,
            sorted(roles_by_emp_id[row["emp_id"]]),
        )
        if created:
            new_accounts.append({
                "emp_id": row["emp_id"],
                "emp_name": row["emp_name"],
                "username": row["emp_id"],
                "password": password,
                "dept_name": row.get("dept_name") or "",
                "roles": ",".join(sorted(roles_by_emp_id[row["emp_id"]])),
            })

    password_file_name = ""
    password_download_url = ""
    if new_accounts:
        password_file_name = _write_password_xlsx(new_accounts, batch_id)
        password_download_url = f"/imports/{batch_id}/account-passwords.xlsx"

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
        "new_account_count": len(new_accounts),
        "password_file": password_file_name,
        "password_download_url": password_download_url,
    }
