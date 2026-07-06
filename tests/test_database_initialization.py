from werkzeug.security import check_password_hash

from performance_app import create_app
from performance_app.db import SCHEMA_VERSION, connect


EXPECTED_TABLES = {
    "schema_version",
    "role_catalog",
    "user_account",
    "user_role",
    "evaluation_cycle",
    "cycle_employee_snapshot",
    "evaluation_record",
    "grade_adjustment_log",
    "objective_data",
    "import_batch",
    "import_error",
    "audit_log",
}


def table_names(db_path, key):
    with connect(db_path, key) as connection:
        rows = connection.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def test_create_app_creates_sqlite_file_and_schema(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"

    app = create_app({"TESTING": True, "DATABASE": str(db_path)})
    key = app.config["DB_ENCRYPTION_KEY"]

    assert db_path.exists()
    assert EXPECTED_TABLES.issubset(table_names(db_path, key))

    with connect(db_path, key) as connection:
        version = connection.execute(
            "select version from schema_version order by id desc limit 1"
        ).fetchone()[0]
        roles = {
            row[0]
            for row in connection.execute("select role_code from role_catalog").fetchall()
        }
        usernames = {
            row[0]
            for row in connection.execute("select username from user_account").fetchall()
        }
        hr = connection.execute(
            "select id, emp_id, username, password_hash, status from user_account where username = 'hr'"
        ).fetchone()
        hr_roles = {
            row[0]
            for row in connection.execute(
                "select role_code from user_role where user_id = ?", (hr[0],)
            ).fetchall()
        }
        cycle_count = connection.execute("select count(*) from evaluation_cycle").fetchone()[0]
        snapshot_count = connection.execute(
            "select count(*) from cycle_employee_snapshot"
        ).fetchone()[0]

    assert version == SCHEMA_VERSION
    assert roles == {
        "EMPLOYEE",
        "DIRECT_MANAGER",
        "INDIRECT_MANAGER",
        "DEPT_HEAD",
        "HRBP",
        "ADMIN",
    }
    # 仅保留初始 hr 账号;不再创建演示员工/上下级/管理员账号
    assert usernames == {"hr"}
    assert hr[1] == "hr"
    assert hr[2] == "hr"
    assert check_password_hash(hr[3], "admin123")
    assert hr[4] == "ACTIVE"
    assert hr_roles == {"HRBP"}
    # 不再 seed 演示周期 / 演示员工快照
    assert cycle_count == 0
    assert snapshot_count == 0


def test_create_app_does_not_destroy_existing_database(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"
    app = create_app({"TESTING": True, "DATABASE": str(db_path)})
    key = app.config["DB_ENCRYPTION_KEY"]

    with connect(db_path, key) as connection:
        connection.execute(
            """
            insert into evaluation_cycle
                (cycle_name, start_date, end_date, status, created_by, created_at)
            values
                ('2026-Q2', '2026-04-01', '2026-06-30', 'PREPARING', 'admin', '2026-06-16T00:00:00')
            """
        )
        connection.commit()

    create_app({"TESTING": True, "DATABASE": str(db_path)})

    with connect(db_path, key) as connection:
        cycles = connection.execute("select cycle_name from evaluation_cycle order by id").fetchall()

    assert cycles == [("2026-Q2",)]
