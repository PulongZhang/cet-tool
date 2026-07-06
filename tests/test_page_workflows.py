import sqlite3

from werkzeug.security import generate_password_hash
from performance_app.db import connect

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
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        return connection.execute("select id from evaluation_record where emp_id = ?", (emp_id,)).fetchone()[0]


SUBJECTIVE_LEVELS = ["A+", "A", "B+", "B", "B-", "C", "D"]


def option_values_after(html, marker, count=7):
    start = html.index(marker)
    select_start = html.index("<select", start)
    select_end = html.index("</select>", select_start)
    select_html = html[select_start:select_end]
    values = []
    position = 0
    while True:
        option_start = select_html.find("<option", position)
        if option_start == -1:
            break
        value_start = select_html.index(">", option_start) + 1
        value_end = select_html.index("</option>", value_start)
        values.append(select_html[value_start:value_end])
        position = value_end
    return values[:count]


def test_dashboard_flow_progress_updates_from_record_statuses(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "HR001", "hr_user", ("HRBP",))
    client = app.test_client()
    seed_cycle_people(client)
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("update evaluation_record set status = 'DIRECT_PENDING' where emp_id = 'E001'")
        connection.commit()
    login(client, "hr_user")

    page = client.get("/?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "当前主要阶段" in html
    assert "直接上级评分" in html
    assert "1 人" in html


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
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
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
    assert "待员工自评" in html
    assert "SELF_PENDING" not in html
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

    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        status = connection.execute("select status from evaluation_record where emp_id = 'E001'").fetchone()[0]
    assert status == "DIRECT_PENDING"


def test_self_review_rating_selects_use_consistent_order(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "E001", "lisi", ("EMPLOYEE",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "lisi")

    page = client.get("/self-review?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert option_values_after(html, "产出和质量") == SUBJECTIVE_LEVELS
    assert option_values_after(html, "主动承担") == SUBJECTIVE_LEVELS
    assert option_values_after(html, "易用性和可维护") == SUBJECTIVE_LEVELS


def test_self_review_page_locks_after_submit(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "E001", "lisi", ("EMPLOYEE",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "lisi")

    client.post(
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

    page = client.get("/self-review?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "自评已提交，等待直接上级评分" in html
    assert "/page/self-submit" not in html
    assert "保存草稿" not in html


def test_self_review_page_actions_ignore_locked_record(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "E001", "lisi", ("EMPLOYEE",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "lisi")
    locked_record_id = str(record_id(app, "E001"))

    client.post(
        "/page/self-submit",
        data={
            "record_id": locked_record_id,
            "cycle_id": "1",
            "self_summary": "首次提交",
            "self_score_1": "A",
            "self_score_2": "B+",
            "self_score_3": "A",
        },
        follow_redirects=False,
    )
    client.post(
        "/page/self-draft",
        data={
            "record_id": locked_record_id,
            "cycle_id": "1",
            "self_summary": "绕过页面修改",
            "self_score_1": "C",
            "self_score_2": "C",
            "self_score_3": "C",
        },
        follow_redirects=False,
    )

    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        row = connection.execute(
            "select self_summary, self_score_1, self_score_2, self_score_3, status from evaluation_record where id = ?",
            (locked_record_id,),
        ).fetchone()

    assert row == ("首次提交", "A", "B+", "A", "DIRECT_PENDING")


def test_direct_manager_page_renders_per_report_scoring_forms(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M001", "manager", ("DIRECT_MANAGER",))
    client = app.test_client()
    seed_cycle_people(client)
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute(
            "update evaluation_record set status = 'DIRECT_PENDING', self_summary = '完成核心工作' where emp_id = 'E001'"
        )
        connection.commit()
    login(client, "manager")

    page = client.get("/direct-reports?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "李四" in html
    assert "待直接上级评分" in html
    assert "DIRECT_PENDING" not in html
    assert "完成核心工作" in html
    assert "/page/manager-draft" in html
    assert "保存李四评分草稿" in html


def test_direct_manager_rating_selects_use_consistent_order(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M001", "manager", ("DIRECT_MANAGER",))
    client = app.test_client()
    seed_cycle_people(client)
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("update evaluation_record set status = 'DIRECT_PENDING' where emp_id = 'E001'")
        connection.commit()
    login(client, "manager")

    page = client.get("/direct-reports?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert option_values_after(html, "产出和质量") == SUBJECTIVE_LEVELS
    assert option_values_after(html, "主动承担") == SUBJECTIVE_LEVELS
    assert option_values_after(html, "易用性和可维护") == SUBJECTIVE_LEVELS
    assert option_values_after(html, "初始总评") == SUBJECTIVE_LEVELS


def test_direct_manager_page_does_not_offer_scoring_before_self_submit(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M001", "manager", ("DIRECT_MANAGER",))
    client = app.test_client()
    seed_cycle_people(client)
    login(client, "manager")

    page = client.get("/direct-reports?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "等待员工提交自评" in html
    assert "/page/manager-draft" not in html


def test_indirect_review_page_adjusts_record_level_from_form(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M002", "indirect_user", ("INDIRECT_MANAGER",))
    client = app.test_client()
    seed_cycle_people(client)
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("update evaluation_record set status = 'INDIRECT_PENDING', current_subjective_level = 'A' where emp_id = 'E001'")
        connection.commit()
    login(client, "indirect_user")

    page = client.get("/reviews/indirect/page?cycle_id=1")
    html = page.get_data(as_text=True)
    adjusted = client.post(
        "/page/record-adjustment",
        data={
            "record_id": str(record_id(app, "E001")),
            "cycle_id": "1",
            "return_to": "/reviews/indirect/page",
            "field_name": "current_subjective_level",
            "after_value": "B+",
            "reason": "统一校准",
        },
        follow_redirects=False,
    )

    assert page.status_code == 200
    assert "/page/record-adjustment" in html
    assert "调整建议等级" in html
    assert option_values_after(html, "调整建议等级") == SUBJECTIVE_LEVELS
    assert adjusted.status_code == 302
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        row = connection.execute("select current_subjective_level from evaluation_record where emp_id = 'E001'").fetchone()
        log_count = connection.execute("select count(*) from grade_adjustment_log where record_id = ?", (record_id(app, "E001"),)).fetchone()[0]
    assert row == ("B+",)
    assert log_count == 1


def test_review_pages_render_scoped_records_and_distribution(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M002", "indirect_user", ("INDIRECT_MANAGER",))
    seed_user(app, "M003", "dept_user", ("DEPT_HEAD",))
    client = app.test_client()
    seed_cycle_people(client)
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("update evaluation_record set status = 'INDIRECT_PENDING', current_subjective_level = 'A' where emp_id = 'E001'")
        connection.commit()

    login(client, "indirect_user")
    indirect = client.get("/reviews/indirect/page?cycle_id=1")
    assert indirect.status_code == 200
    assert "李四" in indirect.get_data(as_text=True)
    assert "/page/indirect-submit" in indirect.get_data(as_text=True)

    client.post("/logout")
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("update evaluation_record set status = 'DEPT_HEAD_PENDING', current_subjective_level = 'A' where emp_id = 'E001'")
        connection.commit()
    login(client, "dept_user")
    dept = client.get("/reviews/dept-head/page?cycle_id=1")
    assert dept.status_code == 200
    assert "李四" in dept.get_data(as_text=True)
    assert "/page/dept-submit" in dept.get_data(as_text=True)


def test_dept_review_rating_select_uses_consistent_order(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, "M003", "dept_user", ("DEPT_HEAD",))
    client = app.test_client()
    seed_cycle_people(client)
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("update evaluation_record set status = 'DEPT_HEAD_PENDING', current_subjective_level = 'B+' where emp_id = 'E001'")
        connection.commit()
    login(client, "dept_user")

    page = client.get("/reviews/dept-head/page?cycle_id=1")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert option_values_after(html, "确认等级") == SUBJECTIVE_LEVELS


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
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
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
