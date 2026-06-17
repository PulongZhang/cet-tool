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
        built_in_accounts = {}
        for username in ("employee", "direct", "indirect", "dept", "hr", "admin"):
            account = connection.execute(
                "select id, emp_id, username, password_hash, status from user_account where username = ?",
                (username,),
            ).fetchone()
            account_roles = {
                row[0]
                for row in connection.execute(
                    """
                    select role_code
                    from user_role
                    where user_id = ?
                    """,
                    (account[0],),
                ).fetchall()
            }
            built_in_accounts[username] = (account, account_roles)

    assert version == 1
    assert roles == {
        "EMPLOYEE",
        "DIRECT_MANAGER",
        "INDIRECT_MANAGER",
        "DEPT_HEAD",
        "HRBP",
        "ADMIN",
    }
    expected_accounts = {
        "employee": {"EMPLOYEE"},
        "direct": {"DIRECT_MANAGER"},
        "indirect": {"INDIRECT_MANAGER"},
        "dept": {"DEPT_HEAD"},
        "hr": {"HRBP"},
        "admin": {"ADMIN", "HRBP"},
    }
    for username, expected_roles in expected_accounts.items():
        account, account_roles = built_in_accounts[username]
        assert account[1] == username
        assert account[2] == username
        assert check_password_hash(account[3], "admin123")
        assert account[4] == "ACTIVE"
        assert account_roles == expected_roles


def test_create_app_seeds_demo_workflow_data(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"

    create_app({"TESTING": True, "DATABASE": str(db_path), "SEED_DEMO_DATA": True})

    with sqlite3.connect(db_path) as connection:
        cycle = connection.execute(
            "select id, cycle_name, status from evaluation_cycle where cycle_name = '2026-Q2 演示周期'"
        ).fetchone()
        snapshots = connection.execute(
            """
            select emp_id, emp_name, group_code, direct_manager_id, indirect_manager_id, dept_head_id
            from cycle_employee_snapshot
            where cycle_id = ?
            order by emp_id
            """,
            (cycle[0],),
        ).fetchall()
        records = connection.execute(
            "select emp_id, status from evaluation_record where cycle_id = ? order by emp_id",
            (cycle[0],),
        ).fetchall()
        objective = connection.execute(
            "select emp_id, diligence_level, discipline_level, learning_level from objective_data where cycle_id = ? and emp_id = 'employee'",
            (cycle[0],),
        ).fetchone()

    assert cycle[1:] == ("2026-Q2 演示周期", "ACTIVE")
    assert snapshots == [
        ("dept", "内置部门负责人", "MANAGEMENT", "dept", "dept", "dept"),
        ("direct", "内置直接上级", "MANAGEMENT", "indirect", "dept", "dept"),
        ("employee", "内置演示员工", "EMPLOYEE_P4_10", "direct", "indirect", "dept"),
        ("indirect", "内置间接上级", "MANAGEMENT", "dept", "dept", "dept"),
    ]
    assert records == [
        ("dept", "SELF_PENDING"),
        ("direct", "SELF_PENDING"),
        ("employee", "SELF_PENDING"),
        ("indirect", "SELF_PENDING"),
    ]
    assert objective == ("employee", "A", "A+", "D")


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
        cycles = connection.execute("select cycle_name from evaluation_cycle order by id").fetchall()

    assert cycles == [("2026-Q2",)]
