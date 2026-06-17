from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_DATABASE = Path("data") / "performance_review.sqlite3"


def backup_database(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_suffix(db_path.suffix + f".bak-reset-reviews-{timestamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def active_snapshot_emp_ids(connection: sqlite3.Connection, cycle_id: int) -> list[str]:
    columns = {
        row[1]
        for row in connection.execute("pragma table_info(cycle_employee_snapshot)").fetchall()
    }
    active_clause = "and active = 1" if "active" in columns else ""
    rows = connection.execute(
        f"""
        select emp_id
        from cycle_employee_snapshot
        where cycle_id = ? {active_clause}
        order by emp_id
        """,
        (cycle_id,),
    ).fetchall()
    return [row[0] for row in rows]


def reset_current_cycle_reviews(database_path: str | Path = DEFAULT_DATABASE) -> dict:
    db_path = Path(database_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    with sqlite3.connect(db_path) as connection:
        connection.execute("pragma foreign_keys = on")
        cycle = connection.execute(
            "select id, cycle_name from evaluation_cycle where status = 'ACTIVE' order by id desc limit 1"
        ).fetchone()
        if cycle is None:
            return {
                "cycle_id": None,
                "cycle_name": None,
                "backup_path": None,
                "deleted_adjustment_logs": 0,
                "deleted_evaluation_records": 0,
                "created_evaluation_records": 0,
            }

    backup_path = backup_database(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute("pragma foreign_keys = on")
        try:
            cycle_id, cycle_name = cycle
            emp_ids = active_snapshot_emp_ids(connection, cycle_id)
            record_ids = [
                row[0]
                for row in connection.execute(
                    "select id from evaluation_record where cycle_id = ?",
                    (cycle_id,),
                ).fetchall()
            ]
            if record_ids:
                placeholders = ",".join("?" for _ in record_ids)
                deleted_logs = connection.execute(
                    f"delete from grade_adjustment_log where record_id in ({placeholders})",
                    record_ids,
                ).rowcount
            else:
                deleted_logs = 0
            deleted_records = connection.execute(
                "delete from evaluation_record where cycle_id = ?",
                (cycle_id,),
            ).rowcount
            for emp_id in emp_ids:
                connection.execute(
                    "insert into evaluation_record (cycle_id, emp_id, status) values (?, ?, 'SELF_PENDING')",
                    (cycle_id, emp_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return {
        "cycle_id": cycle_id,
        "cycle_name": cycle_name,
        "backup_path": str(backup_path),
        "deleted_adjustment_logs": deleted_logs,
        "deleted_evaluation_records": deleted_records,
        "created_evaluation_records": len(emp_ids),
    }


def main() -> None:
    result = reset_current_cycle_reviews()
    if result["cycle_id"] is None:
        print("没有找到进行中的周期，未重置任何评审记录。")
        return
    print(f"当前周期：{result['cycle_name']}（ID: {result['cycle_id']}）")
    print(f"备份文件：{result['backup_path']}")
    print(f"删除调整日志：{result['deleted_adjustment_logs']} 条")
    print(f"删除旧评审记录：{result['deleted_evaluation_records']} 条")
    print(f"新建初始评审记录：{result['created_evaluation_records']} 条")
    print("当前周期已恢复到员工可重新自评的初始状态。")


if __name__ == "__main__":
    main()
