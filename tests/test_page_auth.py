from werkzeug.security import generate_password_hash

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def seed_user(app, emp_id="E001", username="lisi", roles=("EMPLOYEE",)):
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
        user_id = cursor.lastrowid
        for role in roles:
            db.execute("insert into user_role (user_id, role_code) values (?, ?)", (user_id, role))
        db.commit()
        return user_id


def login(client, username="lisi"):
    return client.post("/login", data={"username": username, "password": "secret123"}, follow_redirects=False)


def test_protected_pages_redirect_anonymous_users_to_login(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    response = client.get("/self-review")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login?next=/self-review")


def test_browser_login_stores_session_and_logout_clears_it(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, roles=("EMPLOYEE", "DIRECT_MANAGER"))
    client = app.test_client()

    logged_in = login(client)
    dashboard = client.get("/")
    logged_out = client.post("/logout", follow_redirects=False)
    after_logout = client.get("/")

    assert logged_in.status_code == 302
    assert logged_in.headers["Location"].endswith("/")
    assert dashboard.status_code == 200
    assert "当前用户：lisi" in dashboard.get_data(as_text=True)
    assert logged_out.status_code == 302
    assert logged_out.headers["Location"].endswith("/login")
    assert after_logout.status_code == 302


def test_role_pages_reject_users_without_required_role(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, roles=("EMPLOYEE",))
    client = app.test_client()
    login(client)

    forbidden = client.get("/direct-reports")

    assert forbidden.status_code == 403
    assert "没有权限访问该页面" in forbidden.get_data(as_text=True)


def test_role_navigation_only_shows_allowed_pages(tmp_path):
    app = make_app(tmp_path)
    seed_user(app, roles=("EMPLOYEE", "DIRECT_MANAGER"))
    client = app.test_client()
    login(client)

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert "我的自评" in html
    assert "直接上级评分" in html
    assert "客观数据" not in html
    assert "结果导出" not in html
