import sqlite3

from performance_app import create_app
from performance_app.db import connect


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

    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        rows = connection.execute(
            "select operator_id, operator_name, action, target_type, target_id from audit_log"
        ).fetchall()

    assert rows == [("admin", "管理员", "CREATE_CYCLE", "evaluation_cycle", "1")]


def test_delete_preparing_cycle_and_reject_active_cycle_delete(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})
    client.post("/cycles", json={"cycle_name": "2026-Q3", "start_date": "2026-07-01", "end_date": "2026-09-30"})

    deleted = client.delete("/cycles/1", headers={"X-Operator-Id": "admin", "X-Operator-Name": "管理员"})
    client.post("/cycles/2/start")
    active_delete = client.delete("/cycles/2")

    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": True}
    assert active_delete.status_code == 409
    assert active_delete.get_json() == {"error": "only PREPARING cycles can be deleted"}

    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        cycles = connection.execute("select cycle_name from evaluation_cycle order by id").fetchall()
        delete_audit_count = connection.execute("select count(*) from audit_log where action = 'DELETE_CYCLE'").fetchone()[0]
    assert cycles == [("2026-Q3",)]
    assert delete_audit_count == 1


def test_delete_preparing_cycle_removes_non_cascading_import_batch(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})

    # 准备阶段导入数据会在 import_batch 留下指向该周期的记录；该表无 on delete cascade
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            """
            insert into import_batch (cycle_id, import_type, file_name, total_count, operator_id)
            values (1, 'EMPLOYEE', 'employees.xlsx', 10, 'admin')
            """
        )

    deleted = client.delete("/cycles/1", headers={"X-Operator-Id": "admin", "X-Operator-Name": "管理员"})

    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": True}
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        assert connection.execute("select count(*) from evaluation_cycle").fetchone()[0] == 0
        assert connection.execute("select count(*) from import_batch").fetchone()[0] == 0


def test_delete_preparing_cycle_removes_non_cascading_grade_adjustment_log(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    client.post("/cycles", json={"cycle_name": "2026-Q2", "start_date": "2026-04-01", "end_date": "2026-06-30"})

    # grade_adjustment_log 同时引用 evaluation_cycle 与 evaluation_record，且均无 on delete cascade
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        connection.execute("pragma foreign_keys = on")
        connection.execute(
            "insert into evaluation_record (cycle_id, emp_id, status) values (1, 'emp001', 'SELF_PENDING')"
        )
        connection.execute(
            """
            insert into grade_adjustment_log
                (cycle_id, record_id, stage, adjustment_type, field_name,
                 before_value, after_value, reason, operator_id, operator_name)
            values (1, 1, 'DEPT_HEAD', 'SUGGESTED_LEVEL', 'current_subjective_level',
                    'B', 'A', '校准', 'admin', '管理员')
            """
        )

    deleted = client.delete("/cycles/1", headers={"X-Operator-Id": "admin", "X-Operator-Name": "管理员"})

    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": True}
    with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:
        assert connection.execute("select count(*) from evaluation_cycle").fetchone()[0] == 0
        assert connection.execute("select count(*) from grade_adjustment_log").fetchone()[0] == 0
