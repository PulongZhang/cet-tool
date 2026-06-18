#!/usr/bin/env python3
"""
数据库迁移脚本：为 cycle_employee_snapshot 表添加多级部门和岗位字段

运行方式：python migrate_add_dept_fields.py
"""

import sqlite3
from pathlib import Path

DEFAULT_DATABASE = Path("data") / "performance_review.sqlite3"


def migrate_database(db_path: Path) -> dict:
    """执行数据库迁移"""
    if not db_path.exists():
        return {"success": False, "error": f"数据库文件不存在: {db_path}"}

    try:
        with sqlite3.connect(db_path) as conn:
            # 启用外键约束
            conn.execute("pragma foreign_keys = on")

            # 检查是否已经迁移过
            cursor = conn.execute("pragma table_info(cycle_employee_snapshot)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # 检查是否需要迁移
            required_columns = {"dept_level_1", "dept_level_2", "dept_level_3", "dept_level_4", "post"}
            if required_columns.issubset(existing_columns):
                return {"success": True, "message": "数据库已经包含新字段，无需迁移"}

            # 添加新列
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
            conn.execute("update schema_version set version = 2 where id = (select id from schema_version order by id desc limit 1)")

            conn.commit()
            return {"success": True, "message": "Database migration completed successfully"}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    db_path = DEFAULT_DATABASE
    result = migrate_database(db_path)

    if result["success"]:
        print(f"\n[SUCCESS] {result['message']}")
    else:
        print(f"\n[ERROR] Migration failed: {result.get('error', 'Unknown error')}")
        exit(1)
