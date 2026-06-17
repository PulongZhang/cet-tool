from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g
from werkzeug.security import generate_password_hash

SCHEMA_VERSION = 1
DEFAULT_ACCOUNT_PASSWORD = "admin123"
DEFAULT_BUILT_IN_ACCOUNTS = {
    "employee": ("EMPLOYEE",),
    "direct": ("DIRECT_MANAGER",),
    "indirect": ("INDIRECT_MANAGER",),
    "dept": ("DEPT_HEAD",),
    "hr": ("HRBP",),
    "admin": ("ADMIN", "HRBP"),
}
DEMO_CYCLE_NAME = "2026-Q2 演示周期"
DEMO_EMPLOYEES = (
    {
        "emp_id": "employee",
        "emp_name": "内置演示员工",
        "sequence": "员工序列",
        "level": "P4",
        "group_code": "EMPLOYEE_P4_10",
        "dept_name": "演示部门",
        "direct_manager_id": "direct",
        "indirect_manager_id": "indirect",
        "dept_head_id": "dept",
    },
    {
        "emp_id": "direct",
        "emp_name": "内置直接上级",
        "sequence": "管理序列",
        "level": "不适用",
        "group_code": "MANAGEMENT",
        "dept_name": "演示部门",
        "direct_manager_id": "indirect",
        "indirect_manager_id": "dept",
        "dept_head_id": "dept",
    },
    {
        "emp_id": "indirect",
        "emp_name": "内置间接上级",
        "sequence": "管理序列",
        "level": "不适用",
        "group_code": "MANAGEMENT",
        "dept_name": "演示部门",
        "direct_manager_id": "dept",
        "indirect_manager_id": "dept",
        "dept_head_id": "dept",
    },
    {
        "emp_id": "dept",
        "emp_name": "内置部门负责人",
        "sequence": "管理序列",
        "level": "不适用",
        "group_code": "MANAGEMENT",
        "dept_name": "演示部门",
        "direct_manager_id": "dept",
        "indirect_manager_id": "dept",
        "dept_head_id": "dept",
    },
)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        g.db = connection
    return g.db


def close_db(error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def _connect_database(database_path: str) -> sqlite3.Connection:
    return sqlite3.connect(database_path)


def init_database(app: Flask) -> None:
    database_path = app.config["DATABASE"]
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    with _connect_database(database_path) as connection:
        connection.execute("pragma foreign_keys = on")
        connection.executescript(schema_path().read_text(encoding="utf-8"))
        row = connection.execute(
            "select version from schema_version order by id desc limit 1"
        ).fetchone()
        if row is None:
            connection.execute(
                "insert into schema_version (version, applied_at) values (?, datetime('now'))",
                (SCHEMA_VERSION,),
            )
        elif row[0] > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {row[0]} is newer than application version {SCHEMA_VERSION}"
            )
        ensure_built_in_accounts(connection)
        if app.config.get("SEED_DEMO_DATA", True):
            ensure_demo_workflow_data(connection)
        connection.commit()


def ensure_built_in_accounts(connection: sqlite3.Connection) -> None:
    for username, roles in DEFAULT_BUILT_IN_ACCOUNTS.items():
        row = connection.execute(
            "select id from user_account where username = ?",
            (username,),
        ).fetchone()
        if row is None:
            cursor = connection.execute(
                """
                insert into user_account (emp_id, username, password_hash, status)
                values (?, ?, ?, 'ACTIVE')
                """,
                (username, username, generate_password_hash(DEFAULT_ACCOUNT_PASSWORD)),
            )
            user_id = cursor.lastrowid
        else:
            user_id = row[0]

        for role_code in roles:
            connection.execute(
                "insert or ignore into user_role (user_id, role_code) values (?, ?)",
                (user_id, role_code),
            )


def ensure_demo_workflow_data(connection: sqlite3.Connection) -> None:
    existing_cycle = connection.execute("select id from evaluation_cycle limit 1").fetchone()
    if existing_cycle is not None:
        return

    cursor = connection.execute(
        """
        insert into evaluation_cycle (cycle_name, start_date, end_date, status, created_by)
        values (?, '2026-04-01', '2026-06-30', 'ACTIVE', 'admin')
        """,
        (DEMO_CYCLE_NAME,),
    )
    cycle_id = cursor.lastrowid

    for employee in DEMO_EMPLOYEES:
        connection.execute(
            """
            insert into cycle_employee_snapshot
                (cycle_id, emp_id, emp_name, sequence, level, group_code, dept_name,
                 direct_manager_id, indirect_manager_id, dept_head_id, active)
            values
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                cycle_id,
                employee["emp_id"],
                employee["emp_name"],
                employee["sequence"],
                employee["level"],
                employee["group_code"],
                employee["dept_name"],
                employee["direct_manager_id"],
                employee["indirect_manager_id"],
                employee["dept_head_id"],
            ),
        )
        connection.execute(
            "insert into evaluation_record (cycle_id, emp_id, status) values (?, ?, 'SELF_PENDING')",
            (cycle_id, employee["emp_id"]),
        )

    connection.execute(
        """
        insert into objective_data
            (cycle_id, emp_id, diligence_raw_total, diligence_month_avg, diligence_level,
             discipline_raw_count, discipline_level, learning_hours, learning_rank_pct, learning_level)
        values
            (?, 'employee', 180, 60, 'A', 3, 'A+', 12, 100, 'D')
        """,
        (cycle_id,),
    )


def init_app(app: Flask) -> None:
    init_database(app)
    app.teardown_appcontext(close_db)
