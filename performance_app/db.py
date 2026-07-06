from __future__ import annotations

import sqlcipher3 as sqlite3  # DB-API 2.0 与 sqlite3 一致,提供透明整库加密
from pathlib import Path

from flask import Flask, current_app, g
from werkzeug.security import generate_password_hash

SCHEMA_VERSION = 2
DEFAULT_ACCOUNT_PASSWORD = "admin123"
DEFAULT_BUILT_IN_ACCOUNTS = {
    "hr": ("HRBP",),
}


def connect(database_path: str, encryption_key: str) -> sqlite3.Connection:
    """打开加密数据库连接。密钥错误时立即抛出 DatabaseError(file is not a database)。"""
    connection = sqlite3.connect(database_path)
    connection.execute(f"PRAGMA key = \"x'{encryption_key}'\"")
    connection.execute("pragma foreign_keys = on")
    # 主动触发一次解密,把"密钥错误"前置到连接阶段,而非首次业务查询
    connection.execute("select count(*) from sqlite_master").fetchone()
    return connection


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = connect(
            current_app.config["DATABASE"],
            current_app.config["DB_ENCRYPTION_KEY"],
        )
        connection.row_factory = sqlite3.Row
        g.db = connection
    return g.db


def close_db(error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def _connect_database(database_path: str, encryption_key: str) -> sqlite3.Connection:
    return connect(database_path, encryption_key)


def init_database(app: Flask) -> None:
    database_path = app.config["DATABASE"]
    encryption_key = app.config["DB_ENCRYPTION_KEY"]
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    with _connect_database(database_path, encryption_key) as connection:
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
