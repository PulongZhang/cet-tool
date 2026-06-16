import sqlite3

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def seed_people(client):
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})
    rows = [
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
            "emp_id": "E002",
            "emp_name": "王五",
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
            "emp_name": "间接经理",
            "sequence": "管理序列",
            "level": "不适用",
            "dept_name": "平台研发部",
            "direct_manager_id": "M003",
            "indirect_manager_id": "M003",
            "dept_head_id": "M003",
        },
        {
            "emp_id": "M003",
            "emp_name": "部门负责人",
            "sequence": "管理序列",
            "level": "不适用",
            "dept_name": "平台研发部",
            "direct_manager_id": "M003",
            "indirect_manager_id": "M003",
            "dept_head_id": "M003",
        },
    ]
    client.post("/cycles/1/employees/import", json={"file_name": "employees.xlsx", "rows": rows})


def test_import_objective_data_converts_and_persists_levels(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_people(client)

    response = client.post(
        "/objective/import",
        json={
            "cycle_id": 1,
            "file_name": "objective.xlsx",
            "rows": [
                {
                    "emp_id": "E001",
                    "diligence_month_1": 60,
                    "diligence_month_2": 66,
                    "diligence_month_3": 54,
                    "attendance_exception_count": 1,
                    "log_exception_count": 2,
                    "learning_hours": 10,
                },
                {
                    "emp_id": "E002",
                    "diligence_month_1": 35,
                    "diligence_month_2": 40,
                    "diligence_month_3": 45,
                    "attendance_exception_count": 4,
                    "log_exception_count": 3,
                    "learning_hours": 20,
                },
            ],
        },
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )

    assert response.status_code == 200
    assert response.get_json()["summary"] == {"total_count": 2, "success_count": 2, "failed_count": 0}

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        objective_rows = connection.execute(
            """
            select emp_id, diligence_raw_total, diligence_month_avg, diligence_level,
                   discipline_raw_count, discipline_level, learning_hours, learning_rank_pct, learning_level
            from objective_data
            order by emp_id
            """
        ).fetchall()
        audit_count = connection.execute("select count(*) from audit_log where action = 'IMPORT_OBJECTIVE_DATA'").fetchone()[0]

    assert objective_rows == [
        ("E001", 180.0, 60.0, "A", 3, "A+", 10.0, 100.0, "D"),
        ("E002", 120.0, 40.0, "B", 7, "B", 20.0, 50.0, "B+"),
    ]
    assert audit_count == 1


def test_import_objective_data_records_row_errors(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_people(client)

    response = client.post(
        "/objective/import",
        json={
            "cycle_id": 1,
            "file_name": "objective.xlsx",
            "rows": [
                {
                    "emp_id": "E001",
                    "diligence_month_1": -1,
                    "diligence_month_2": 20,
                    "diligence_month_3": 20,
                    "attendance_exception_count": 0,
                    "log_exception_count": 0,
                    "learning_hours": 10,
                },
                {
                    "emp_id": "E999",
                    "diligence_month_1": 20,
                    "diligence_month_2": 20,
                    "diligence_month_3": 20,
                    "attendance_exception_count": 0,
                    "log_exception_count": 0,
                    "learning_hours": 10,
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["summary"] == {"total_count": 2, "success_count": 0, "failed_count": 2}
    assert response.get_json()["errors"] == [
        {"row_number": 2, "emp_id": "E001", "field_name": "diligence_month_1", "error_message": "diligence_month_1 cannot be negative"},
        {"row_number": 3, "emp_id": "E999", "field_name": "emp_id", "error_message": "emp_id does not exist in cycle"},
    ]

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        objective_count = connection.execute("select count(*) from objective_data").fetchone()[0]
        errors = connection.execute(
            "select row_number, emp_id, field_name, error_message from import_error order by row_number"
        ).fetchall()

    assert objective_count == 0
    assert errors == [
        (2, "E001", "diligence_month_1", "diligence_month_1 cannot be negative"),
        (3, "E999", "emp_id", "emp_id does not exist in cycle"),
    ]


def user_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from user_account where emp_id = ?", (emp_id,)).fetchone()[0]


def record_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from evaluation_record where emp_id = ?", (emp_id,)).fetchone()[0]


def move_employee_to_hr_pending(client, app, emp_id):
    employee_user_id = user_id(app, emp_id)
    manager_user_id = user_id(app, "M001")
    indirect_user_id = user_id(app, "M002")
    dept_head_user_id = user_id(app, "M003")
    employee_record_id = record_id(app, emp_id)
    client.post(
        f"/records/{employee_record_id}/self-submit",
        json={"self_summary": "完成核心工作", "self_score_1": "A", "self_score_2": "B+", "self_score_3": "A"},
        headers={"X-User-Id": str(employee_user_id)},
    )
    client.post(
        f"/records/{employee_record_id}/manager-submit",
        json={
            "manager_score_1": "A",
            "manager_score_2": "A",
            "manager_score_3": "B+",
            "initial_total_grade": "A",
            "manager_comment": "表现优秀",
        },
        headers={"X-User-Id": str(manager_user_id)},
    )
    client.post("/reviews/indirect/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(indirect_user_id)})
    client.post("/reviews/dept-head/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(dept_head_user_id)})
    return employee_record_id


def import_valid_objectives(client):
    client.post(
        "/objective/import",
        json={
            "cycle_id": 1,
            "file_name": "objective.xlsx",
            "rows": [
                {
                    "emp_id": "E001",
                    "diligence_month_1": 60,
                    "diligence_month_2": 66,
                    "diligence_month_3": 54,
                    "attendance_exception_count": 4,
                    "log_exception_count": 3,
                    "learning_hours": 20,
                },
                {
                    "emp_id": "E002",
                    "diligence_month_1": 35,
                    "diligence_month_2": 40,
                    "diligence_month_3": 45,
                    "attendance_exception_count": 8,
                    "log_exception_count": 5,
                    "learning_hours": 10,
                },
            ],
        },
    )


def test_calculate_cycle_persists_ranked_results_and_detail(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_people(client)
    first_record_id = move_employee_to_hr_pending(client, app, "E001")
    move_employee_to_hr_pending(client, app, "E002")
    import_valid_objectives(client)

    response = client.post(
        "/cycles/1/calculate",
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )

    assert response.status_code == 200
    assert response.get_json()["summary"] == {"calculated_count": 2}

    results = client.get("/cycles/1/results")
    assert results.status_code == 200
    records = results.get_json()["records"]
    assert records[0]["emp_id"] == "E001"
    assert records[0]["weighted_score"] == 89.9
    assert records[0]["rank_in_group"] == 1
    assert records[0]["rank_total"] == 2
    assert records[0]["suggested_level"] == "B+"
    assert records[0]["final_level"] == "B+"
    assert records[0]["status"] == "INITIAL_CALCULATED"

    detail = client.get(f"/records/{first_record_id}/calculation-detail")
    assert detail.status_code == 200
    assert detail.get_json()["detail"]["contributions"] == {
        "subjective_1": 27.9,
        "subjective_2": 23.2,
        "subjective_3": 25.8,
        "diligence": 4.7,
        "discipline": 4.0,
        "learning": 4.3,
    }

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        audit_count = connection.execute("select count(*) from audit_log where action = 'CALCULATE_RESULTS'").fetchone()[0]
    assert audit_count == 1


def test_calculate_cycle_reports_missing_objective_data(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_people(client)
    move_employee_to_hr_pending(client, app, "E001")

    response = client.post("/cycles/1/calculate")

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "calculation prerequisites not met",
        "missing": [{"record_id": record_id(app, "E001"), "emp_id": "E001", "field_name": "objective_data"}],
    }


def test_hr_final_level_adjustment_requires_reason_and_writes_log(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_people(client)
    first_record_id = move_employee_to_hr_pending(client, app, "E001")
    move_employee_to_hr_pending(client, app, "E002")
    import_valid_objectives(client)
    client.post("/cycles/1/calculate")

    missing_reason = client.post(f"/records/{first_record_id}/final-level", json={"final_level": "A"})
    assert missing_reason.status_code == 400
    assert missing_reason.get_json() == {"error": "final_level and reason are required"}

    adjusted = client.post(
        f"/records/{first_record_id}/final-level",
        json={"final_level": "A", "reason": "HR 最终微调"},
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )

    assert adjusted.status_code == 200
    assert adjusted.get_json()["record"]["suggested_level"] == "B+"
    assert adjusted.get_json()["record"]["final_level"] == "A"

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        adjustment = connection.execute(
            "select stage, adjustment_type, field_name, before_value, after_value, reason from grade_adjustment_log"
        ).fetchone()
    assert adjustment == ("HR", "FINAL_LEVEL", "final_level", "B+", "A", "HR 最终微调")
