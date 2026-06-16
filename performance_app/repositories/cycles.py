from __future__ import annotations

from sqlite3 import IntegrityError, Row

from performance_app.db import get_db


def row_to_cycle(row: Row) -> dict:
    return {
        "id": row["id"],
        "cycle_name": row["cycle_name"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "status": row["status"],
        "created_by": row["created_by"],
    }


def list_cycles() -> list[dict]:
    rows = get_db().execute(
        """
        select id, cycle_name, start_date, end_date, status, created_by
        from evaluation_cycle
        order by id desc
        """
    ).fetchall()
    return [row_to_cycle(row) for row in rows]


def get_cycle(cycle_id: int) -> dict | None:
    row = get_db().execute(
        """
        select id, cycle_name, start_date, end_date, status, created_by
        from evaluation_cycle
        where id = ?
        """,
        (cycle_id,),
    ).fetchone()
    return row_to_cycle(row) if row else None


def create_cycle(cycle_name: str, start_date: str, end_date: str, created_by: str) -> dict:
    try:
        cursor = get_db().execute(
            """
            insert into evaluation_cycle
                (cycle_name, start_date, end_date, status, created_by)
            values
                (?, ?, ?, 'PREPARING', ?)
            """,
            (cycle_name, start_date, end_date, created_by),
        )
    except IntegrityError as exc:
        raise ValueError(f"cycle already exists: {cycle_name}") from exc
    return get_cycle(cursor.lastrowid)


def has_active_cycle(excluding_cycle_id: int | None = None) -> bool:
    if excluding_cycle_id is None:
        row = get_db().execute(
            "select id from evaluation_cycle where status = 'ACTIVE' limit 1"
        ).fetchone()
    else:
        row = get_db().execute(
            "select id from evaluation_cycle where status = 'ACTIVE' and id != ? limit 1",
            (excluding_cycle_id,),
        ).fetchone()
    return row is not None


def update_cycle_status(cycle_id: int, expected_status: str, new_status: str) -> dict | None:
    cursor = get_db().execute(
        """
        update evaluation_cycle
        set status = ?
        where id = ? and status = ?
        """,
        (new_status, cycle_id, expected_status),
    )
    if cursor.rowcount == 0:
        return None
    return get_cycle(cycle_id)
