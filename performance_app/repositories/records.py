from __future__ import annotations

from sqlite3 import Row

from performance_app.db import get_db


def row_to_record(row: Row) -> dict:
    return {key: row[key] for key in row.keys()}


def get_record(record_id: int) -> dict | None:
    row = get_db().execute(
        """
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.id = ?
        """,
        (record_id,),
    ).fetchone()
    return row_to_record(row) if row else None


def get_my_record(cycle_id: int, emp_id: str) -> dict | None:
    row = get_db().execute(
        """
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and r.emp_id = ?
        """,
        (cycle_id, emp_id),
    ).fetchone()
    return row_to_record(row) if row else None


def list_direct_reports(cycle_id: int, manager_emp_id: str) -> list[dict]:
    rows = get_db().execute(
        """
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and s.direct_manager_id = ? and r.emp_id != ?
        order by r.emp_id
        """,
        (cycle_id, manager_emp_id, manager_emp_id),
    ).fetchall()
    return [row_to_record(row) for row in rows]


def update_self_review(record_id: int, payload: dict, status: str) -> dict:
    get_db().execute(
        """
        update evaluation_record
        set self_summary = ?, self_score_1 = ?, self_score_2 = ?, self_score_3 = ?,
            status = ?, submitted_at = datetime('now'), updated_at = datetime('now')
        where id = ?
        """,
        (
            payload.get("self_summary"),
            payload.get("self_score_1"),
            payload.get("self_score_2"),
            payload.get("self_score_3"),
            status,
            record_id,
        ),
    )
    return get_record(record_id)


def update_manager_score(record_id: int, payload: dict, status: str) -> dict:
    get_db().execute(
        """
        update evaluation_record
        set manager_score_1 = ?, manager_score_2 = ?, manager_score_3 = ?, manager_comment = ?,
            initial_total_grade = ?, current_subjective_level = ?,
            final_subjective_grade_1 = ?, final_subjective_grade_2 = ?, final_subjective_grade_3 = ?,
            status = ?, submitted_at = datetime('now'), updated_at = datetime('now')
        where id = ?
        """,
        (
            payload.get("manager_score_1"),
            payload.get("manager_score_2"),
            payload.get("manager_score_3"),
            payload.get("manager_comment"),
            payload.get("initial_total_grade"),
            payload.get("initial_total_grade"),
            payload.get("manager_score_1"),
            payload.get("manager_score_2"),
            payload.get("manager_score_3"),
            status,
            record_id,
        ),
    )
    return get_record(record_id)


def list_review_records(cycle_id: int, scope_field: str, emp_id: str, status: str) -> list[dict]:
    rows = get_db().execute(
        f"""
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and s.{scope_field} = ? and r.emp_id != ? and r.status = ?
        order by r.emp_id
        """,
        (cycle_id, emp_id, emp_id, status),
    ).fetchall()
    return [row_to_record(row) for row in rows]


def distribution_for_records(records: list[dict]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for record in records:
        level = record.get("current_subjective_level") or "未评分"
        distribution[level] = distribution.get(level, 0) + 1
    return distribution


def update_record_field(record_id: int, field_name: str, after_value: str) -> dict:
    allowed = {
        "current_subjective_level",
        "final_subjective_grade_1",
        "final_subjective_grade_2",
        "final_subjective_grade_3",
        "final_level",
    }
    if field_name not in allowed:
        raise ValueError(f"Unsupported adjustment field: {field_name}")
    get_db().execute(
        f"update evaluation_record set {field_name} = ?, updated_at = datetime('now') where id = ?",
        (after_value, record_id),
    )
    return get_record(record_id)


def list_scope_records(cycle_id: int, scope_field: str, emp_id: str) -> list[dict]:
    rows = get_db().execute(
        f"""
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and s.{scope_field} = ? and r.emp_id != ?
        order by r.emp_id
        """,
        (cycle_id, emp_id, emp_id),
    ).fetchall()
    return [row_to_record(row) for row in rows]


def bulk_update_status(cycle_id: int, scope_field: str, emp_id: str, from_status: str, to_status: str) -> int:
    cursor = get_db().execute(
        f"""
        update evaluation_record
        set status = ?, submitted_at = datetime('now'), updated_at = datetime('now')
        where cycle_id = ?
          and status = ?
          and emp_id in (
              select emp_id from cycle_employee_snapshot
              where cycle_id = ? and {scope_field} = ? and emp_id != ?
          )
        """,
        (to_status, cycle_id, from_status, cycle_id, emp_id, emp_id),
    )
    return cursor.rowcount


def submit_direct_report_drafts(cycle_id: int, manager_emp_id: str) -> int:
    cursor = get_db().execute(
        """
        update evaluation_record
        set status = 'INDIRECT_PENDING', submitted_at = datetime('now'), updated_at = datetime('now')
        where cycle_id = ?
          and status = 'DIRECT_DRAFT'
          and emp_id in (
              select emp_id from cycle_employee_snapshot
              where cycle_id = ? and direct_manager_id = ? and emp_id != ?
          )
        """,
        (cycle_id, cycle_id, manager_emp_id, manager_emp_id),
    )
    return cursor.rowcount


def update_status(record_id: int, status: str) -> dict:
    get_db().execute(
        "update evaluation_record set status = ?, updated_at = datetime('now') where id = ?",
        (status, record_id),
    )
    return get_record(record_id)
