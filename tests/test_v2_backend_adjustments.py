import sqlite3

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def create_cycle(client):
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})


def employee_rows():
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


def test_employee_list_and_import_error_query(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_cycle(client)

    imported = client.post("/cycles/1/employees/import", json={"file_name": "employees.xlsx", "rows": employee_rows()})
    assert imported.status_code == 200
    batch_id = imported.get_json()["batch_id"]

    employees = client.get("/cycles/1/employees")
    assert employees.status_code == 200
    assert [row["emp_id"] for row in employees.get_json()["employees"]] == ["E001", "M001", "M002", "M003"]

    no_errors = client.get(f"/imports/{batch_id}/errors")
    assert no_errors.status_code == 200
    assert no_errors.get_json()["errors"] == []

    invalid_rows = employee_rows()[:1] + [
        {
            "emp_id": "E002",
            "emp_name": "非法职级",
            "sequence": "员工序列",
            "level": "P11",
            "dept_name": "平台研发部",
            "direct_manager_id": "M001",
            "indirect_manager_id": "M002",
            "dept_head_id": "M003",
        }
    ]
    failed = client.post("/cycles/1/employees/import", json={"file_name": "employees.xlsx", "rows": invalid_rows})
    assert failed.status_code == 200
    error_batch_id = failed.get_json()["batch_id"]

    errors = client.get(f"/imports/{error_batch_id}/errors")
    assert errors.status_code == 200
    assert errors.get_json()["errors"] == [
        {"row_number": 3, "emp_id": "E002", "field_name": "level", "error_message": "Unsupported employee level: P11"}
    ]


def employee_rows_with_two_reports():
    rows = employee_rows()
    rows.insert(
        1,
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
    )
    return rows


def seed_two_reports(client):
    create_cycle(client)
    client.post("/cycles/1/employees/import", json={"file_name": "employees.xlsx", "rows": employee_rows_with_two_reports()})


def user_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from user_account where emp_id = ?", (emp_id,)).fetchone()[0]


def record_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from evaluation_record where emp_id = ?", (emp_id,)).fetchone()[0]


def submit_self(client, app, emp_id):
    client.post(
        f"/records/{record_id(app, emp_id)}/self-submit",
        json={"self_summary": "完成工作", "self_score_1": "A", "self_score_2": "B+", "self_score_3": "A"},
        headers={"X-User-Id": str(user_id(app, emp_id))},
    )


def save_manager_draft(client, app, emp_id):
    client.post(
        f"/records/{record_id(app, emp_id)}/manager-draft",
        json={
            "manager_score_1": "A",
            "manager_score_2": "A",
            "manager_score_3": "B+",
            "initial_total_grade": "A",
            "manager_comment": "表现优秀",
        },
        headers={"X-User-Id": str(user_id(app, "M001"))},
    )


def test_direct_manager_batch_submit_requires_all_reports_ready(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_two_reports(client)
    submit_self(client, app, "E001")
    save_manager_draft(client, app, "E001")

    blocked = client.post(
        "/records/direct-reports/submit",
        json={"cycle_id": 1},
        headers={"X-User-Id": str(user_id(app, "M001"))},
    )

    assert blocked.status_code == 409
    assert blocked.get_json() == {
        "error": "not all direct reports are ready to submit",
        "blocking_records": [{"record_id": record_id(app, "E002"), "emp_id": "E002", "status": "SELF_PENDING"}],
    }

    submit_self(client, app, "E002")
    save_manager_draft(client, app, "E002")
    submitted = client.post(
        "/records/direct-reports/submit",
        json={"cycle_id": 1},
        headers={"X-User-Id": str(user_id(app, "M001"))},
    )

    assert submitted.status_code == 200
    assert submitted.get_json() == {"updated_count": 2}

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        statuses = connection.execute("select emp_id, status from evaluation_record where emp_id in ('E001', 'E002') order by emp_id").fetchall()
    assert statuses == [("E001", "INDIRECT_PENDING"), ("E002", "INDIRECT_PENDING")]


def test_indirect_and_dept_submit_require_full_scope_ready(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_two_reports(client)
    submit_self(client, app, "E001")
    client.post(
        f"/records/{record_id(app, 'E001')}/manager-submit",
        json={
            "manager_score_1": "A",
            "manager_score_2": "A",
            "manager_score_3": "B+",
            "initial_total_grade": "A",
            "manager_comment": "表现优秀",
        },
        headers={"X-User-Id": str(user_id(app, "M001"))},
    )
    submit_self(client, app, "E002")

    indirect_blocked = client.post(
        "/reviews/indirect/submit",
        json={"cycle_id": 1},
        headers={"X-User-Id": str(user_id(app, "M002"))},
    )

    assert indirect_blocked.status_code == 409
    assert indirect_blocked.get_json() == {
        "error": "not all scoped records are ready to submit",
        "blocking_records": [{"record_id": record_id(app, "E002"), "emp_id": "E002", "status": "DIRECT_PENDING"}],
    }

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("update evaluation_record set status = 'DEPT_HEAD_PENDING' where emp_id = 'E001'")
        connection.execute("update evaluation_record set status = 'INDIRECT_PENDING' where emp_id = 'E002'")
        connection.commit()

    dept_blocked = client.post(
        "/reviews/dept-head/submit",
        json={"cycle_id": 1},
        headers={"X-User-Id": str(user_id(app, "M003"))},
    )

    assert dept_blocked.status_code == 409
    assert dept_blocked.get_json() == {
        "error": "not all scoped records are ready to submit",
        "blocking_records": [{"record_id": record_id(app, "E002"), "emp_id": "E002", "status": "INDIRECT_PENDING"}],
    }


def move_two_reports_to_hr_pending(client, app):
    for emp_id in ("E001", "E002"):
        submit_self(client, app, emp_id)
        save_manager_draft(client, app, emp_id)
    client.post(
        "/records/direct-reports/submit",
        json={"cycle_id": 1},
        headers={"X-User-Id": str(user_id(app, "M001"))},
    )
    client.post("/reviews/indirect/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(user_id(app, "M002"))})
    client.post("/reviews/dept-head/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(user_id(app, "M003"))})


def objective_rows():
    return [
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
    ]


def import_objectives(client):
    return client.post("/objective/import", json={"cycle_id": 1, "file_name": "objective.xlsx", "rows": objective_rows()})


def objective_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from objective_data where emp_id = ?", (emp_id,)).fetchone()[0]


def test_objective_correction_requires_reason_and_audits(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_two_reports(client)
    import_objectives(client)
    e001_objective_id = objective_id(app, "E001")

    missing_reason = client.post(f"/objective/{e001_objective_id}/correct", json={"diligence_level": "B"})
    assert missing_reason.status_code == 400
    assert missing_reason.get_json() == {"error": "reason and at least one objective level are required"}

    corrected = client.post(
        f"/objective/{e001_objective_id}/correct",
        json={"diligence_level": "B", "learning_level": "A", "reason": "中途入职人工修正"},
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )

    assert corrected.status_code == 200
    assert corrected.get_json()["objective"]["diligence_level"] == "B"
    assert corrected.get_json()["objective"]["learning_level"] == "A"
    assert corrected.get_json()["objective"]["corrected"] == 1

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        row = connection.execute(
            "select diligence_level, learning_level, corrected, correction_reason from objective_data where id = ?",
            (e001_objective_id,),
        ).fetchone()
        audit_count = connection.execute("select count(*) from audit_log where action = 'CORRECT_OBJECTIVE_DATA'").fetchone()[0]
    assert row == ("B", "A", 1, "中途入职人工修正")
    assert audit_count == 1


def test_reimport_objectives_invalidates_calculated_results(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_two_reports(client)
    move_two_reports_to_hr_pending(client, app)
    import_objectives(client)
    calculated = client.post("/cycles/1/calculate", headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"})
    assert calculated.status_code == 200

    reimported = import_objectives(client)
    assert reimported.status_code == 200

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        rows = connection.execute(
            "select emp_id, status, weighted_score, rank_in_group, suggested_level, final_level from evaluation_record where emp_id in ('E001', 'E002') order by emp_id"
        ).fetchall()
    assert rows == [
        ("E001", "HR_PENDING", None, None, None, None),
        ("E002", "HR_PENDING", None, None, None, None),
    ]


def prepare_calculated_cycle(client, app):
    seed_two_reports(client)
    move_two_reports_to_hr_pending(client, app)
    import_objectives(client)
    response = client.post("/cycles/1/calculate", headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"})
    assert response.status_code == 200


def test_finalize_results_locks_status_but_allows_audited_final_adjustment(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    prepare_calculated_cycle(client, app)
    e001_record_id = record_id(app, "E001")

    finalized = client.post(
        "/cycles/1/results/finalize",
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )

    assert finalized.status_code == 200
    assert finalized.get_json() == {"updated_count": 2}

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        status_rows = connection.execute(
            "select emp_id, status from evaluation_record where emp_id in ('E001', 'E002') order by emp_id"
        ).fetchall()
        before_score = connection.execute("select weighted_score from evaluation_record where emp_id = 'E001'").fetchone()[0]
    assert status_rows == [("E001", "FINAL_CONFIRMED"), ("E002", "FINAL_CONFIRMED")]

    adjusted = client.post(
        f"/records/{e001_record_id}/final-level",
        json={"final_level": "A", "reason": "最终确认后微调"},
        headers={"X-Operator-Id": "hr001", "X-Operator-Name": "HR"},
    )
    assert adjusted.status_code == 200
    assert adjusted.get_json()["record"]["final_level"] == "A"

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        after_row = connection.execute(
            "select status, weighted_score, final_level from evaluation_record where emp_id = 'E001'"
        ).fetchone()
        finalize_audit_count = connection.execute("select count(*) from audit_log where action = 'FINALIZE_RESULTS'").fetchone()[0]
        adjustment = connection.execute(
            "select stage, adjustment_type, field_name, before_value, after_value, reason from grade_adjustment_log order by id desc limit 1"
        ).fetchone()
    assert after_row == ("FINAL_CONFIRMED", before_score, "A")
    assert finalize_audit_count == 1
    assert adjustment == ("HR", "FINAL_LEVEL", "final_level", "B+", "A", "最终确认后微调")
