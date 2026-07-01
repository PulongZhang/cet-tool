from __future__ import annotations

from sqlite3 import Row

from performance_app.db import get_db


def row_to_record(row: Row) -> dict:
    return {key: row[key] for key in row.keys()}


def get_record(record_id: int) -> dict | None:
    row = get_db().execute(
        """
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level, s.sequence
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
        select r.*, s.emp_name, s.dept_name, s.dept_level_1, s.dept_level_2, s.dept_level_3, s.dept_level_4, s.post,
               s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level, s.sequence
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
        select r.*, s.emp_name, s.dept_name, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level, s.sequence
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
        select r.*, s.emp_name, s.dept_name, s.dept_level_4, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level, s.sequence
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and s.{scope_field} = ? and r.emp_id != ? and r.status = ?
        order by r.emp_id
        """,
        (cycle_id, emp_id, emp_id, status),
    ).fetchall()
    records = [row_to_record(row) for row in rows]

    # 获取每个记录的最新调整记录（建议等级调整）
    for record in records:
        adjustment = get_db().execute(
            """
            select before_value, after_value, reason, operator_name
            from grade_adjustment_log
            where record_id = ? and field_name = 'current_subjective_level'
            order by adjusted_at desc limit 1
            """,
            (record["id"],),
        ).fetchone()
        if adjustment:
            record["adjustment"] = {
                "before_value": adjustment["before_value"],
                "after_value": adjustment["after_value"],
                "reason": adjustment["reason"],
                "operator_name": adjustment["operator_name"],
            }

    return records


def distribution_for_records(records: list[dict]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for record in records:
        level = record.get("current_subjective_level") or "未评分"
        distribution[level] = distribution.get(level, 0) + 1
    return distribution


def level_range_distributions(records: list[dict]) -> dict:
    """
    计算不同职级范围的分布数据

    返回格式:
    {
        "p1_p3": {"distribution": {...}, "total": N},
        "p4_p10": {"distribution": {...}, "total": N},
        "overall": {"distribution": {...}, "total": N}
    }
    """
    p1_p3_records = []
    p4_p10_records = []

    for record in records:
        level = record.get("level", "")
        if level in ["P1", "P2", "P3"]:
            p1_p3_records.append(record)
        elif level in ["P4", "P5", "P6", "P7", "P8", "P9", "P10"]:
            p4_p10_records.append(record)

    p1_p3_dist = _aggregate_distribution(distribution_for_records(p1_p3_records))
    p4_p10_dist = _aggregate_distribution(distribution_for_records(p4_p10_records))
    overall_dist = _aggregate_distribution(distribution_for_records(records))

    return {
        "p1_p3": {"distribution": p1_p3_dist, "total": len(p1_p3_records)},
        "p4_p10": {"distribution": p4_p10_dist, "total": len(p4_p10_records)},
        "overall": {"distribution": overall_dist, "total": len(records)},
    }


def _aggregate_distribution(dist: dict[str, int]) -> dict[str, int]:
    """
    聚合分布数据：A+A合并、B+B合并、B-独立、C和D合并
    """
    return {
        "A": dist.get("A+", 0) + dist.get("A", 0),
        "B": dist.get("B+", 0) + dist.get("B", 0),
        "B-": dist.get("B-", 0),
        "C/D": dist.get("C", 0) + dist.get("D", 0),
    }


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
        select r.*, s.emp_name, s.dept_name, s.dept_level_4, s.direct_manager_id, s.indirect_manager_id, s.dept_head_id, s.group_code, s.level, s.sequence
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        where r.cycle_id = ? and s.{scope_field} = ? and r.emp_id != ?
        order by s.sequence desc, s.level, r.emp_id
        """,
        (cycle_id, emp_id, emp_id),
    ).fetchall()
    records = [row_to_record(row) for row in rows]

    # 获取每个记录的最新调整记录（建议等级调整）
    for record in records:
        adjustment = get_db().execute(
            """
            select before_value, after_value, reason, operator_name
            from grade_adjustment_log
            where record_id = ? and field_name = 'current_subjective_level'
            order by adjusted_at desc limit 1
            """,
            (record["id"],),
        ).fetchone()
        if adjustment:
            record["adjustment"] = {
                "before_value": adjustment["before_value"],
                "after_value": adjustment["after_value"],
                "reason": adjustment["reason"],
                "operator_name": adjustment["operator_name"],
            }

        # 计算职级范围
        level = record.get("level", "")
        if level in ["P1", "P2", "P3"]:
            record["level_range"] = "P1-P3"
        elif level in ["P4", "P5", "P6", "P7", "P8", "P9", "P10"]:
            record["level_range"] = "P4-P10"
        else:
            record["level_range"] = level or "-"

    return records


def filter_records(records: list[dict], filter_status: str, filter_level: str, filter_dept: str, filter_level_range: str = "") -> list[dict]:
    """筛选记录列表"""
    filtered = records
    if filter_status:
        filtered = [r for r in filtered if r.get("status") == filter_status]
    if filter_level:
        filtered = [r for r in filtered if r.get("level") == filter_level]
    if filter_level_range:
        filtered = [r for r in filtered if r.get("level_range") == filter_level_range]
    if filter_dept:
        filtered = [r for r in filtered if r.get("dept_level_4") == filter_dept or r.get("dept_name") == filter_dept]
    return filtered


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
    # 当间接上级和部门负责人是同一个人时，自动跳过间接上级审阅环节
    # 直接将状态变为 DEPT_HEAD_PENDING，并确保 current_subjective_level 已设置
    cursor_skip = get_db().execute(
        """
        update evaluation_record
        set status = 'DEPT_HEAD_PENDING',
            current_subjective_level = coalesce(current_subjective_level, initial_total_grade),
            submitted_at = datetime('now'),
            updated_at = datetime('now')
        where cycle_id = ?
          and status = 'DIRECT_DRAFT'
          and emp_id in (
              select emp_id from cycle_employee_snapshot
              where cycle_id = ? and direct_manager_id = ? and indirect_manager_id = dept_head_id and emp_id != ?
          )
        """,
        (cycle_id, cycle_id, manager_emp_id, manager_emp_id),
    )
    # 当间接上级和部门负责人不是同一个人时，状态变为 INDIRECT_PENDING
    # 并确保 current_subjective_level 已设置
    cursor_normal = get_db().execute(
        """
        update evaluation_record
        set status = 'INDIRECT_PENDING',
            current_subjective_level = coalesce(current_subjective_level, initial_total_grade),
            submitted_at = datetime('now'),
            updated_at = datetime('now')
        where cycle_id = ?
          and status = 'DIRECT_DRAFT'
          and emp_id in (
              select emp_id from cycle_employee_snapshot
              where cycle_id = ? and direct_manager_id = ? and indirect_manager_id != dept_head_id and emp_id != ?
          )
        """,
        (cycle_id, cycle_id, manager_emp_id, manager_emp_id),
    )
    return cursor_skip.rowcount + cursor_normal.rowcount


def update_status(record_id: int, status: str) -> dict:
    get_db().execute(
        "update evaluation_record set status = ?, updated_at = datetime('now') where id = ?",
        (status, record_id),
    )
    return get_record(record_id)


def list_records_by_statuses(cycle_id: int, statuses: list[str]) -> list[dict]:
    """根据状态列表获取考核记录（用于HR查看各阶段明细）"""
    placeholders = ",".join("?" * len(statuses))
    rows = get_db().execute(
        f"""
        select r.*,
               s.emp_name, s.dept_name, s.dept_level_4,
               s.direct_manager_id, s.indirect_manager_id, s.dept_head_id,
               s.group_code, s.level,
               dm.emp_name as direct_manager_name,
               im.emp_name as indirect_manager_name,
               dh.emp_name as dept_head_name
        from evaluation_record r
        join cycle_employee_snapshot s on s.cycle_id = r.cycle_id and s.emp_id = r.emp_id
        left join cycle_employee_snapshot dm on dm.cycle_id = s.cycle_id and dm.emp_id = s.direct_manager_id
        left join cycle_employee_snapshot im on im.cycle_id = s.cycle_id and im.emp_id = s.indirect_manager_id
        left join cycle_employee_snapshot dh on dh.cycle_id = s.cycle_id and dh.emp_id = s.dept_head_id
        where r.cycle_id = ? and r.status in ({placeholders})
          and s.group_code != 'EXCLUDED'
        order by r.emp_id
        """,
        (cycle_id, *statuses),
    ).fetchall()
    return [row_to_record(row) for row in rows]
