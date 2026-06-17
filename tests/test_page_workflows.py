import sqlite3

from werkzeug.security import generate_password_hash

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def seed_user(app, emp_id, username, roles):
    with app.app_context():
        from performance_app.db import get_db

        db = get_db()
        cursor = db.execute(
            """
            insert into user_account (emp_id, username, password_hash, status)
            values (?, ?, ?, 'ACTIVE')
            """,
            (emp_id, username, generate_password_hash("secret123")),
        )
        for role in roles:
            db.execute("insert into user_role (user_id, role_code) values (?, ?)", (cursor.lastrowid, role))
        db.commit()
        return cursor.lastrowid


def login(client, username):
    client.post("/login", data={"username": username, "password": "secret123"})


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


def seed_cycle_people(client):
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})
    client.post("/cycles/1/employees/import", json={"file_name": "employees.xlsx", "rows": employee_rows()})


def record_id(app, emp_id):
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        return connection.execute("select id from evaluation_record where emp_id = ?", (emp_id,)).fetchone()[0]


def test_cycle_management_page_renders_for_hr_and_hides_cycle_id_label(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "HR001", "hr_user", ("HRBP",))
    client = app.test_client()
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})
    client.post("/cycles/1/start")
    client.post("/cycles", json={"cycle_name": "2026-Q3", "start_date": "2026-07-01", "end_date": "2026-09-30"})
    login(client, "hr_user")

    page = client.get("/cycles/page")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "周期管理" in html
    assert "2026-Q2" in html
    assert "周期 ID" not in html
    assert "/page/cycles/create" in html
    assert "/page/cycles/start" in html
    assert "/page/cycles/close" in html
    assert "/page/cycles/delete" in html


def test_cycle_management_page_rejects_employee_role(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "E001", "lisi", ("EMPLOYEE",))
    client = app.test_client()
    login(client, "lisi")

    page = client.get("/cycles/page")

    assert page.status_code == 403


def test_cycle_management_page_actions_manage_cycle_statuses(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "HR001", "hr_user", ("HRBP",))
    client = app.test_client()
    login(client, "hr_user")

    created = client.post(
        "/page/cycles/create",
        data={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"},
        follow_redirects=False,
    )
    started = client.post("/page/cycles/start", data={"cycle_id": "1"}, follow_redirects=False)
    closed = client.post("/page/cycles/close", data={"cycle_id": "1"}, follow_redirects=False)
    client.post(
        "/page/cycles/create",
        data={"cycle_name": "2026-Q3", "start_date": "2026-07-01", "end_date": "2026-09-30"},
        follow_redirects=False,
    )
    deleted = client.post("/page/cycles/delete", data={"cycle_id": "2"}, follow_redirects=False)

    assert created.status_code == 302
    assert started.status_code == 302
    assert closed.status_code == 302
    assert deleted.status_code == 302
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        cycles = connection.execute("select cycle_name, status from evaluation_cycle order by id").fetchall()
        actions = connection.execute("select action from audit_log order by id").fetchall()
    assert cycles == [("2026-Q2", "CLOSED")]
    assert actions == [("CREATE_CYCLE",), ("START_CYCLE",), ("CLOSE_CYCLE",), ("CREATE_CYCLE",), ("DELETE_CYCLE",)]


def test_self_review_page_renders_record_and_submit_form_updates_status(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "E001", "lisi", ("EMPLOYEE",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "lisi")

    page = client.get("/self-review?cycle_id=1")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "李四" in html
    assert "SELF_PENDING" in html
    assert "/page/self-submit" in html

    submitted = client.post(
        "/page/self-submit",
        data={
            "record_id": str(record_id(app, "E001")),
            "cycle_id": "1",
            "self_summary": "完成核心工作",
            "self_score_1": "A",
            "self_score_2": "B+",
            "self_score_3": "A",
        },
        follow_redirects=False,
    )
    assert submitted.status_code == 302

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        status = connection.execute("select status from evaluation_record where emp_id = 'E001'").fetchone()[0]
    assert status == "DIRECT_PENDING"


def test_direct_manager_page_renders_reports_and_draft_form(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M001", "manager", ("DIRECT_MANAGER",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "manager")

    page = client.get("/direct-reports?cycle_id=1")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "李四" in html
    assert "SELF_PENDING" in html
    assert "/page/manager-draft" in html


def test_review_pages_render_scoped_records_and_distribution(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M002", "indirect_user", ("INDIRECT_MANAGER",))
    seed_user(app, "M003", "dept_user", ("DEPT_HEAD",))
    client = app.test_client()
    seed_cycle_people(client)
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("update evaluation_record set status = 'INDIRECT_PENDING', current_subjective_level = 'A' where emp_id = 'E001'")
        connection.commit()

    login(client, "indirect_user")
    indirect = client.get("/reviews/indirect/page?cycle_id=1")
    assert indirect.status_code == 200
    assert "李四" in indirect.get_data(as_text=True)
    assert "/page/indirect-submit" in indirect.get_data(as_text=True)

    client.post("/logout")
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute("update evaluation_record set status = 'DEPT_HEAD_PENDING', current_subjective_level = 'A' where emp_id = 'E001'")
        connection.commit()
    login(client, "dept_user")
    dept = client.get("/reviews/dept-head/page?cycle_id=1")
    assert dept.status_code == 200
    assert "李四" in dept.get_data(as_text=True)
    assert "/page/dept-submit" in dept.get_data(as_text=True)


def test_objective_page_uses_browser_upload_action(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "HR001", "hr_user", ("HRBP",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "hr_user")

    page = client.get("/objective/import/page?cycle_id=1")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "/page/objective-upload" in html
    assert "/objective/template" in html
    assert "周期 ID" not in html
    assert "2026-Q2" in html


def test_objective_upload_without_file_redirects_without_error(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "HR001", "hr_user", ("HRBP",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "hr_user")

    response = client.post("/page/objective-upload", data={"cycle_id": "1"}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/objective/import/page?cycle_id=1")


def test_hr_results_page_renders_calculated_records(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "HR001", "hr_user", ("HRBP",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "hr_user")
    with sqlite3.connect(app.config["DATABASE"]) as connection:
        connection.execute(
            """
            update evaluation_record
            set status = 'INITIAL_CALCULATED', weighted_score = 89.9, rank_in_group = 1,
                rank_total = 1, suggested_level = 'B+', final_level = 'B+'
            where emp_id = 'E001'
            """
        )
        connection.commit()

    page = client.get("/results?cycle_id=1")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "李四" in html
    assert "89.9" in html
    assert "/page/calculate" in html
    assert "/page/export-final" in html
