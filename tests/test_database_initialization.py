import sqlite3

from werkzeug.security import check_password_hash

from performance_app import create_app


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


def table_names(db_path):
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def test_create_app_creates_sqlite_file_and_schema(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"

    create_app({"TESTING": True, "DATABASE": str(db_path)})

    assert db_path.exists()
    assert EXPECTED_TABLES.issubset(table_names(db_path))

    with sqlite3.connect(db_path) as connection:
        version = connection.execute(
            "select version from schema_version order by id desc limit 1"
        ).fetchone()[0]
        roles = {
            row[0]
            for row in connection.execute("select role_code from role_catalog").fetchall()
        }
        admin_row = connection.execute(
            "select id, emp_id, username, password_hash, status from user_account where username = 'admin'"
        ).fetchone()
        admin_roles = {
            row[0]
            for row in connection.execute(
                """
                select role_code
                from user_role
                where user_id = ?
                """,
                (admin_row[0],),
            ).fetchall()
        }

    assert version == 1
    assert roles == {
        "EMPLOYEE",
        "DIRECT_MANAGER",
        "INDIRECT_MANAGER",
        "DEPT_HEAD",
        "HRBP",
        "ADMIN",
    }
    assert admin_row[1] == "admin"
    assert admin_row[2] == "admin"
    assert check_password_hash(admin_row[3], "admin123")
    assert admin_row[4] == "ACTIVE"
    assert admin_roles == {"ADMIN", "HRBP"}


def test_create_app_does_not_destroy_existing_database(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"
    create_app({"TESTING": True, "DATABASE": str(db_path)})

    with sqlite3.connect(db_path) as connection:
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

    with sqlite3.connect(db_path) as connection:
        count = connection.execute("select count(*) from evaluation_cycle").fetchone()[0]

    assert count == 1
