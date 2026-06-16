import sqlite3

from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def test_create_and_list_cycles(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    create_response = client.post(
        "/cycles",
        json={
            "cycle_name": "2026-Q2",
            "start_date": "2026-04-01",
            "end_date": "2026-06-30",
        },
        headers={"X-Operator-Id": "admin", "X-Operator-Name": "管理员"},
    )

    assert create_response.status_code == 201
    assert create_response.get_json()["cycle"] == {
        "id": 1,
        "cycle_name": "2026-Q2",
        "start_date": "2026-04-01",
        "end_date": "2026-06-30",
        "status": "PREPARING",
        "created_by": "admin",
    }

    list_response = client.get("/cycles")

    assert list_response.status_code == 200
    assert list_response.get_json()["cycles"][0]["cycle_name"] == "2026-Q2"


def test_create_cycle_requires_name_and_dates(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    response = client.post("/cycles", json={"cycle_name": "2026-Q2"})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "cycle_name, start_date, and end_date are required"
    }


def test_start_cycle_allows_only_one_active_cycle(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})
    client.post("/cycles", json={"cycle_name": "2026-Q3", "start_date": "2026-07-01", "end_date": "2026-09-30"})

    first_start = client.post("/cycles/1/start")
    second_start = client.post("/cycles/2/start")

    assert first_start.status_code == 200
    assert first_start.get_json()["cycle"]["status"] == "ACTIVE"
    assert second_start.status_code == 409
    assert second_start.get_json() == {"error": "another ACTIVE cycle already exists"}


def test_cycle_actions_write_audit_log(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    client.post(
        "/cycles",
        json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"},
        headers={"X-Operator-Id": "admin", "X-Operator-Name": "管理员"},
    )

    with sqlite3.connect(app.config["DATABASE"]) as connection:
        rows = connection.execute(
            "select operator_id, operator_name, action, target_type, target_id from audit_log"
        ).fetchall()

    assert rows == [("admin", "管理员", "CREATE_CYCLE", "evaluation_cycle", "1")]
