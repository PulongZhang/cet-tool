import sqlite3

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def seed_cycle_people(client):
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


def user_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from user_account where emp_id = ?", (emp_id,)).fetchone()[0]


def record_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from evaluation_record where emp_id = ?", (emp_id,)).fetchone()[0]


def submit_self_and_manager(client, app):
    manager_user_id = user_id(app, "M001")
    employee_user_id = user_id(app, "E001")
    employee_record_id = record_id(app, "E001")
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
    return employee_record_id


def test_employee_self_review_flow(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_cycle_people(client)
    employee_user_id = user_id(app, "E001")
    employee_record_id = record_id(app, "E001")

    mine = client.get("/records/my?cycle_id=1", headers={"X-User-Id": str(employee_user_id)})
    assert mine.status_code == 200
    assert mine.get_json()["record"]["emp_id"] == "E001"

    draft = client.post(
        f"/records/{employee_record_id}/self-draft",
        json={"self_summary": "完成核心工作", "self_score_1": "A", "self_score_2": "B+", "self_score_3": "A"},
        headers={"X-User-Id": str(employee_user_id)},
    )
    assert draft.status_code == 200
    assert draft.get_json()["record"]["status"] == "SELF_DRAFT"

    submitted = client.post(
        f"/records/{employee_record_id}/self-submit",
        json={"self_summary": "完成核心工作", "self_score_1": "A", "self_score_2": "B+", "self_score_3": "A"},
        headers={"X-User-Id": str(employee_user_id)},
    )
    assert submitted.status_code == 200
    assert submitted.get_json()["record"]["status"] == "DIRECT_PENDING"


def test_direct_manager_scoring_flow_and_comment_rule(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_cycle_people(client)
    manager_user_id = user_id(app, "M001")
    employee_user_id = user_id(app, "E001")
    employee_record_id = record_id(app, "E001")
    client.post(
        f"/records/{employee_record_id}/self-submit",
        json={"self_summary": "完成核心工作", "self_score_1": "A", "self_score_2": "B+", "self_score_3": "A"},
        headers={"X-User-Id": str(employee_user_id)},
    )

    reports = client.get("/records/direct-reports?cycle_id=1", headers={"X-User-Id": str(manager_user_id)})
    assert reports.status_code == 200
    assert [record["emp_id"] for record in reports.get_json()["records"]] == ["E001"]

    missing_comment = client.post(
        f"/records/{employee_record_id}/manager-submit",
        json={"manager_score_1": "A", "manager_score_2": "A", "manager_score_3": "B+", "initial_total_grade": "A"},
        headers={"X-User-Id": str(manager_user_id)},
    )
    assert missing_comment.status_code == 400
    assert missing_comment.get_json() == {"error": "manager_comment is required for A+, A, C, or D"}

    submitted = client.post(
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
    assert submitted.status_code == 200
    record = submitted.get_json()["record"]
    assert record["status"] == "INDIRECT_PENDING"
    assert record["current_subjective_level"] == "A"
    assert record["final_subjective_grade_1"] == "A"
    assert record["final_subjective_grade_2"] == "A"
    assert record["final_subjective_grade_3"] == "B+"


def test_indirect_adjustment_distribution_submit_and_withdraw(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_cycle_people(client)
    employee_record_id = submit_self_and_manager(client, app)
    indirect_user_id = user_id(app, "M002")

    review_list = client.get("/reviews/indirect?cycle_id=1", headers={"X-User-Id": str(indirect_user_id)})
    assert review_list.status_code == 200
    assert [record["emp_id"] for record in review_list.get_json()["records"]] == ["E001"]

    distribution = client.get("/reviews/indirect/distribution?cycle_id=1", headers={"X-User-Id": str(indirect_user_id)})
    assert distribution.status_code == 200
    assert distribution.get_json()["distribution"] == {"A": 1}

    adjusted = client.post(
        f"/records/{employee_record_id}/adjustments",
        json={"field_name": "current_subjective_level", "after_value": "B+", "reason": "统一校准"},
        headers={"X-User-Id": str(indirect_user_id)},
    )
    assert adjusted.status_code == 200
    assert adjusted.get_json()["record"]["current_subjective_level"] == "B+"

    submitted = client.post("/reviews/indirect/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(indirect_user_id)})
    assert submitted.status_code == 200
    assert submitted.get_json()["updated_count"] == 1

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        status = connection.execute("select status from evaluation_record where id = ?", (employee_record_id,)).fetchone()[0]
        log_count = connection.execute("select count(*) from grade_adjustment_log where record_id = ?", (employee_record_id,)).fetchone()[0]
    assert status == "DEPT_HEAD_PENDING"
    assert log_count == 1

    withdrawn = client.post(
        f"/records/{employee_record_id}/withdraw",
        json={"reason": "退回间接审阅"},
        headers={"X-User-Id": str(indirect_user_id)},
    )
    assert withdrawn.status_code == 200
    assert withdrawn.get_json()["record"]["status"] == "INDIRECT_PENDING"


def test_dept_head_submit_moves_records_to_hr_pending(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    seed_cycle_people(client)
    submit_self_and_manager(client, app)
    indirect_user_id = user_id(app, "M002")
    dept_head_user_id = user_id(app, "M003")
    client.post("/reviews/indirect/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(indirect_user_id)})

    dept_list = client.get("/reviews/dept-head?cycle_id=1", headers={"X-User-Id": str(dept_head_user_id)})
    assert dept_list.status_code == 200
    assert [record["emp_id"] for record in dept_list.get_json()["records"]] == ["E001"]

    submitted = client.post("/reviews/dept-head/submit", json={"cycle_id": 1}, headers={"X-User-Id": str(dept_head_user_id)})
    assert submitted.status_code == 200
    assert submitted.get_json()["updated_count"] == 1

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        status = connection.execute("select status from evaluation_record where emp_id = 'E001'").fetchone()[0]
    assert status == "HR_PENDING"
