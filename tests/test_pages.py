from werkzeug.security import generate_password_hash

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def seed_user(app, roles):
    with app.app_context():
        from performance_app.db import get_db

        db = get_db()
        cursor = db.execute(
            """
            insert into user_account (emp_id, username, password_hash, status)
            values ('E001', 'lisi', ?, 'ACTIVE')
            """,
            (generate_password_hash("secret123"),),
        )
        for role in roles:
            db.execute("insert into user_role (user_id, role_code) values (?, ?)", (cursor.lastrowid, role))
        db.commit()


def login(client):
    client.post("/login", data={"username": "lisi", "password": "secret123"})


def assert_page_contains(client, path, expected_texts):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for text in expected_texts:
        assert text in html


def test_login_and_dashboard_pages_render(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, ("EMPLOYEE", "HRBP"))
    client = app.test_client()
    login(client)

    assert_page_contains(client, "/login", ["绩效考核评分工具", "用户名", "密码", "/login"])
    assert_page_contains(client, "/", ["首页仪表盘", "我的自评", "计算结果与导出"])


def test_workflow_role_pages_render_core_sections(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, ("EMPLOYEE", "DIRECT_MANAGER", "INDIRECT_MANAGER", "DEPT_HEAD"))
    client = app.test_client()
    login(client)

    assert_page_contains(client, "/self-review", ["我的自评", "我的考核记录", "没有找到"])
    assert_page_contains(client, "/direct-reports", ["直接上级评分", "下属列表", "暂无下属记录"])
    assert_page_contains(client, "/reviews/indirect/page", ["间接上级审阅", "比例分布", "暂无待审阅记录"])
    assert_page_contains(client, "/reviews/dept-head/page", ["部门负责人确认", "暂无待确认记录"])


def test_hr_pages_render_import_results_and_export_controls(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, ("HRBP",))
    client = app.test_client()
    login(client)

    assert_page_contains(client, "/objective/import/page", ["客观数据导入", "objective.xlsx", "/page/objective-upload", "/objective/template"])
    assert_page_contains(client, "/results", ["计算结果与导出", "执行计算", "最终确认", "/page/export-final"])


def test_pages_do_not_show_raw_cycle_id_field(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, ("EMPLOYEE", "DIRECT_MANAGER", "INDIRECT_MANAGER", "DEPT_HEAD", "HRBP"))
    client = app.test_client()
    login(client)

    for path in ["/self-review", "/direct-reports", "/reviews/indirect/page", "/reviews/dept-head/page", "/objective/import/page", "/results"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "周期 ID" not in response.get_data(as_text=True)
