from __future__ import annotations

import secrets
import string
from sqlite3 import Row

from werkzeug.security import generate_password_hash

from performance_app.db import get_db


def row_to_user(row: Row, roles: list[str]) -> dict:
    return {
        "id": row["id"],
        "emp_id": row["emp_id"],
        "username": row["username"],
        "roles": sorted(roles),
    }


def roles_for_user(user_id: int) -> list[str]:
    rows = get_db().execute(
        "select role_code from user_role where user_id = ? order by role_code",
        (user_id,),
    ).fetchall()
    return [row["role_code"] for row in rows]


def find_by_username(username: str) -> dict | None:
    row = get_db().execute(
        "select id, emp_id, username, password_hash, status from user_account where username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    user = row_to_user(row, roles_for_user(row["id"]))
    user["password_hash"] = row["password_hash"]
    user["status"] = row["status"]
    return user


def find_by_id(user_id: int) -> dict | None:
    row = get_db().execute(
        "select id, emp_id, username, status from user_account where id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    user = row_to_user(row, roles_for_user(row["id"]))
    user["status"] = row["status"]
    return user


def create_account(emp_id: str, username: str, password: str, roles: list[str]) -> dict:
    cursor = get_db().execute(
        """
        insert into user_account (emp_id, username, password_hash, status)
        values (?, ?, ?, 'ACTIVE')
        """,
        (emp_id, username, generate_password_hash(password)),
    )
    user_id = cursor.lastrowid
    for role in sorted(set(roles)):
        get_db().execute(
            "insert or ignore into user_role (user_id, role_code) values (?, ?)",
            (user_id, role),
        )
    return find_by_id(user_id)


PASSWORD_ALPHABET = string.ascii_letters + string.digits
PASSWORD_LENGTH = 10


def generate_random_password() -> str:
    """生成长度为 10 的随机字母数字密码(无特殊字符,便于分发与输入)。"""
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def ensure_account(emp_id: str, username: str, password: str, roles: list[str]) -> tuple[dict, bool]:
    """确保账号存在。返回 (user, created):created 为 True 表示本次新建,调用方据此收集初始密码。"""
    row = get_db().execute(
        "select id from user_account where emp_id = ?",
        (emp_id,),
    ).fetchone()
    if row is None:
        return create_account(emp_id, username, password, roles), True

    for role in sorted(set(roles)):
        get_db().execute(
            "insert or ignore into user_role (user_id, role_code) values (?, ?)",
            (row["id"], role),
        )
    return find_by_id(row["id"]), False
