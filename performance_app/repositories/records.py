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
