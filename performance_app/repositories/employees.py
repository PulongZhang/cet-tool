from __future__ import annotations

from performance_app.db import get_db


def upsert_snapshot(cycle_id: int, row: dict, group_code: str) -> None:
    get_db().execute(
        """
        insert into cycle_employee_snapshot
            (cycle_id, emp_id, emp_name, sequence, level, group_code, dept_name,
             direct_manager_id, indirect_manager_id, dept_head_id, active)
        values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        on conflict(cycle_id, emp_id) do update set
            emp_name = excluded.emp_name,
            sequence = excluded.sequence,
            level = excluded.level,
            group_code = excluded.group_code,
            dept_name = excluded.dept_name,
            direct_manager_id = excluded.direct_manager_id,
            indirect_manager_id = excluded.indirect_manager_id,
            dept_head_id = excluded.dept_head_id,
            active = excluded.active
        """,
        (
            cycle_id,
            row["emp_id"],
            row["emp_name"],
            row["sequence"],
            row["level"],
            group_code,
            row["dept_name"],
            row["direct_manager_id"],
            row["indirect_manager_id"],
            row["dept_head_id"],
        ),
    )


def ensure_evaluation_record(cycle_id: int, emp_id: str) -> None:
    get_db().execute(
        """
        insert or ignore into evaluation_record (cycle_id, emp_id, status)
        values (?, ?, 'SELF_PENDING')
        """,
        (cycle_id, emp_id),
    )


def create_import_batch(cycle_id: int, import_type: str, file_name: str, total_count: int, operator_id: str) -> int:
    cursor = get_db().execute(
        """
        insert into import_batch
            (cycle_id, import_type, file_name, total_count, success_count, failed_count, operator_id)
        values
            (?, ?, ?, ?, 0, 0, ?)
        """,
        (cycle_id, import_type, file_name, total_count, operator_id),
    )
    return cursor.lastrowid


def update_import_batch_counts(batch_id: int, success_count: int, failed_count: int) -> None:
    get_db().execute(
        "update import_batch set success_count = ?, failed_count = ? where id = ?",
        (success_count, failed_count, batch_id),
    )


def add_import_error(batch_id: int, error: dict, raw_data: dict) -> None:
    get_db().execute(
        """
        insert into import_error
            (batch_id, row_number, emp_id, field_name, error_message, raw_data)
        values
            (?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            error["row_number"],
            error.get("emp_id"),
            error["field_name"],
            error["error_message"],
            str(raw_data),
        ),
    )
