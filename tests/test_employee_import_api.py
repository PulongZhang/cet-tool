import sqlite3

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def create_cycle(client):
    response = client.post(
        "/cycles",
        json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"},
    )
    assert response.status_code == 201


def valid_rows():
    return [
        {
            "emp_id": "E001",
            "emp_name": "李四",
            "sequence": "员工序列",
            "level": "P4",
            "dept_name": "平台研发部",
            "direct_manager_id": "M001",
            "indirect_manager_id": "M002",
            "dept_head_id": "M003",
        },
        {
            "emp_id": "M001",
            "emp_name": "张三",
            "sequence": "管理序列",
            "level": "不适用",
            "dept_name": "平台研发部",
            "direct_manager_id": "M002",
            "indirect_manager_id": "M003",
            "dept_head_id": "M003",
        },
        {
            "emp_id": "M002",
            "emp_name": "王经理",
            "sequence": "管理序列",
            "level": "不适用",
            "dept_name": "平台研发部",
            "direct_manager_id": "M003",
            "indirect_manager_id": "M003",
            "dept_head_id": "M003",
        },
        {
            "emp_id": "M003",
            "emp_name": "部门经理",
            "sequence": "管理序列",
            "level": "不适用",
            "dept_name": "平台研发部",
            "direct_manager_id": "M003",
            "indirect_manager_id": "M003",
            "dept_head_id": "M003",
        },
    ]


def test_import_employees_creates_snapshots_records_accounts_and_roles(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_cycle(client)

    response = client.post(
        "/cycles/1/employees/import",
        json={"file_name": "employees.xlsx", "rows": valid_rows()},
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )

    assert response.status_code == 200
    assert response.get_json()["summary"] == {"total_count": 4, "success_count": 4, "failed_count": 0}

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        snapshots = connection.execute(
            "select emp_id, group_code from cycle_employee_snapshot order by emp_id"
        ).fetchall()
        records = connection.execute(
            "select emp_id, status from evaluation_record order by emp_id"
        ).fetchall()
        role_rows = connection.execute(
            """
            select u.emp_id, r.role_code
            from user_account u
            join user_role r on r.user_id = u.id
            order by u.emp_id, r.role_code
            """
        ).fetchall()

    assert snapshots == [
        ("E001", "EMPLOYEE_P4_10"),
        ("M001", "MANAGEMENT"),
        ("M002", "MANAGEMENT"),
        ("M003", "MANAGEMENT"),
    ]
    assert records == [
        ("E001", "SELF_PENDING"),
        ("M001", "SELF_PENDING"),
        ("M002", "SELF_PENDING"),
        ("M003", "SELF_PENDING"),
    ]
    assert ("E001", "EMPLOYEE") in role_rows
    assert ("M001", "DIRECT_MANAGER") in role_rows
    assert ("M002", "INDIRECT_MANAGER") in role_rows
    assert ("M003", "DEPT_HEAD") in role_rows


def test_import_employees_records_duplicate_and_invalid_level_errors(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_cycle(client)
    rows = valid_rows()[:1] + [
        {
            "emp_id": "E001",
            "emp_name": "重复员工",
            "sequence": "员工序列",
            "level": "P1",
            "dept_name": "平台研发部",
            "direct_manager_id": "M001",
            "indirect_manager_id": "M002",
            "dept_head_id": "M003",
        },
        {
            "emp_id": "E002",
            "emp_name": "非法职级",
            "sequence": "员工序列",
            "level": "P11",
            "dept_name": "平台研发部",
            "direct_manager_id": "M001",
            "indirect_manager_id": "M002",
            "dept_head_id": "M003",
        },
    ]

    response = client.post("/cycles/1/employees/import", json={"file_name": "employees.xlsx", "rows": rows})

    assert response.status_code == 200
    assert response.get_json()["summary"] == {"total_count": 3, "success_count": 0, "failed_count": 2}
    assert response.get_json()["errors"] == [
        {"row_number": 3, "emp_id": "E001", "field_name": "emp_id", "error_message": "duplicate emp_id in import file"},
        {"row_number": 4, "emp_id": "E002", "field_name": "level", "error_message": "Unsupported employee level: P11"},
    ]

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        errors = connection.execute(
            "select row_number, emp_id, field_name, error_message from import_error order by row_number"
        ).fetchall()
        snapshot_count = connection.execute("select count(*) from cycle_employee_snapshot").fetchone()[0]

    assert errors == [
        (3, "E001", "emp_id", "duplicate emp_id in import file"),
        (4, "E002", "level", "Unsupported employee level: P11"),
    ]
    assert snapshot_count == 0
