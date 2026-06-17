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


def init_app(app: Flask) -> None:
    init_database(app)
    app.teardown_appcontext(close_db)
