from werkzeug.security import generate_password_hash

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def seed_user(app):
    with app.app_context():
        from performance_app.db import get_db

        db = get_db()
        cursor = db.execute(
            """
            insert into user_account (emp_id, username, password_hash, status)
            values (?, ?, ?, 'ACTIVE')
            """,
            ("E001", "lisi", generate_password_hash("secret123")),
        )
        user_id = cursor.lastrowid
        db.execute("insert into user_role (user_id, role_code) values (?, ?)", (user_id, "EMPLOYEE"))
        db.execute("insert into user_role (user_id, role_code) values (?, ?)", (user_id, "DIRECT_MANAGER"))
        db.commit()
        return user_id


def test_login_accepts_valid_password_and_returns_roles(tmp_path):
    app = make_app(tmp_path)
    seed_user(app)
    client = app.test_client()

    response = client.post("/auth/login", json={"username": "lisi", "password": "secret123"})

    assert response.status_code == 200
    assert response.get_json() == {
        "user": {
            "id": 1,
            "emp_id": "E001",
            "username": "lisi",
            "roles": ["DIRECT_MANAGER", "EMPLOYEE"],
        }
    }


def test_login_rejects_wrong_password(tmp_path):
    app = make_app(tmp_path)
    seed_user(app)
    client = app.test_client()

    response = client.post("/auth/login", json={"username": "lisi", "password": "wrong"})

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid username or password"}


def test_me_returns_user_from_header(tmp_path):
    app = make_app(tmp_path)
    user_id = seed_user(app)
    client = app.test_client()

    response = client.get("/auth/me", headers={"X-User-Id": str(user_id)})

    assert response.status_code == 200
    assert response.get_json()["user"]["emp_id"] == "E001"
    assert response.get_json()["user"]["roles"] == ["DIRECT_MANAGER", "EMPLOYEE"]


def test_me_requires_user_header(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.get_json() == {"error": "X-User-Id header is required"}
