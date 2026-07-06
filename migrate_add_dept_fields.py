#!/usr/bin/env python3
"""
数据库迁移脚本：为 cycle_employee_snapshot 表添加多级部门和岗位字段。

加密改造后需通过 DB_ENCRYPTION_KEY 环境变量提供密钥：
    DB_ENCRYPTION_KEY=<密钥> python migrate_add_dept_fields.py
"""
from __future__ import annotations

import os
from pathlib import Path

from performance_app.db import connect

DEFAULT_DATABASE = Path("data") / "performance_review.sqlite3"


def migrate_database(db_path: str | Path = DEFAULT_DATABASE, encryption_key: str | None = None) -> dict:
    """执行数据库迁移:为旧库补 dept_level_1..4 / post 列。"""
    if not Path(db_path).exists():
        return {"success": False, "error": f"数据库文件不存在: {db_path}"}

    key = encryption_key or os.environ.get("DB_ENCRYPTION_KEY")
    if not key:
        return {"success": False, "error": "未设置 DB_ENCRYPTION_KEY 环境变量"}

    try:
        with connect(str(db_path), key) as conn:
            # 检查是否已经迁移过
            cursor = conn.execute("pragma table_info(cycle_employee_snapshot)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            required_columns = {"dept_level_1", "dept_level_2", "dept_level_3", "dept_level_4", "post"}
            if required_columns.issubset(existing_columns):
                return {"success": True, "message": "数据库已经包含新字段，无需迁移"}

            # 添加缺失的列
            new_columns = [
                ("dept_level_1", "text"),
                ("dept_level_2", "text"),
                ("dept_level_3", "text"),
                ("dept_level_4", "text"),
                ("post", "text"),
            ]

            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    conn.execute(f"alter table cycle_employee_snapshot add column {col_name} {col_type}")
                    print(f"[OK] Added column: {col_name}")

            # 更新 schema_version
            conn.execute(
                "update schema_version set version = 2 "
                "where id = (select id from schema_version order by id desc limit 1)"
            )

            conn.commit()
            return {"success": True, "message": "Database migration completed successfully"}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = migrate_database(DEFAULT_DATABASE)
    if result["success"]:
        print(f"\n[SUCCESS] {result['message']}")
    else:
        print(f"\n[ERROR] Migration failed: {result.get('error', 'Unknown error')}")
        exit(1)
