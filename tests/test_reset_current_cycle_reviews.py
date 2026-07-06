from pathlib import Path

from performance_app.db import connect
from reset_current_cycle_reviews import reset_current_cycle_reviews

KEY = "a" * 64  # 测试用固定密钥


def create_schema(connection):
    connection.executescript(
        """
        create table evaluation_cycle (
            id integer primary key autoincrement,
            cycle_name text not null,
            status text not null
        );
        create table cycle_employee_snapshot (
            id integer primary key autoincrement,
            cycle_id integer not null,
            emp_id text not null,
            emp_name text not null,
            active integer not null default 1
        );
        create table evaluation_record (
            id integer primary key autoincrement,
            cycle_id integer not null,
            emp_id text not null,
            status text not null,
            self_summary text,
            unique(cycle_id, emp_id)
        );
        create table grade_adjustment_log (
            id integer primary key autoincrement,
            cycle_id integer not null,
            record_id integer not null,
            reason text not null
        );
        create table objective_data (
            id integer primary key autoincrement,
            cycle_id integer not null,
            emp_id text not null
        );
        """
    )


def seed_data(db_path):
    with connect(db_path, KEY) as connection:
        create_schema(connection)
        connection.execute("insert into evaluation_cycle (id, cycle_name, status) values (1, '2026-Q2', 'ACTIVE')")
        connection.execute("insert into evaluation_cycle (id, cycle_name, status) values (2, '2026-Q1', 'CLOSED')")
        connection.execute("insert into cycle_employee_snapshot (cycle_id, emp_id, emp_name, active) values (1, 'E001', '李四', 1)")
        connection.execute("insert into cycle_employee_snapshot (cycle_id, emp_id, emp_name, active) values (1, 'E002', '王五', 1)")
        connection.execute("insert into cycle_employee_snapshot (cycle_id, emp_id, emp_name, active) values (1, 'E003', '停用员工', 0)")
        connection.execute("insert into objective_data (cycle_id, emp_id) values (1, 'E001')")
        connection.execute("insert into evaluation_record (id, cycle_id, emp_id, status, self_summary) values (11, 1, 'E001', 'DIRECT_PENDING', '已提交')")
        connection.execute("insert into evaluation_record (id, cycle_id, emp_id, status, self_summary) values (12, 1, 'E002', 'INDIRECT_PENDING', '已评分')")
        connection.execute("insert into evaluation_record (id, cycle_id, emp_id, status, self_summary) values (21, 2, 'H001', 'FINAL_CONFIRMED', '历史')")
        connection.execute("insert into grade_adjustment_log (cycle_id, record_id, reason) values (1, 11, '调整')")
        connection.execute("insert into grade_adjustment_log (cycle_id, record_id, reason) values (2, 21, '历史')")
        connection.commit()


def test_reset_current_cycle_reviews_backs_up_deletes_and_recreates_active_cycle_reviews(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"
    seed_data(db_path)

    result = reset_current_cycle_reviews(db_path, KEY)

    assert result["cycle_id"] == 1
    assert result["cycle_name"] == "2026-Q2"
    assert result["deleted_evaluation_records"] == 2
    assert result["deleted_adjustment_logs"] == 1
    assert result["created_evaluation_records"] == 2
    assert Path(result["backup_path"]).exists()
    with connect(db_path, KEY) as connection:
        cycles = connection.execute("select id, cycle_name, status from evaluation_cycle order by id").fetchall()
        snapshots = connection.execute("select cycle_id, emp_id, emp_name from cycle_employee_snapshot where cycle_id = 1 order by emp_id").fetchall()
        objectives = connection.execute("select cycle_id, emp_id from objective_data").fetchall()
        records = connection.execute("select cycle_id, emp_id, status, self_summary from evaluation_record order by cycle_id, emp_id").fetchall()
        logs = connection.execute("select cycle_id, record_id, reason from grade_adjustment_log order by id").fetchall()

    assert cycles == [(1, "2026-Q2", "ACTIVE"), (2, "2026-Q1", "CLOSED")]
    assert snapshots == [(1, "E001", "李四"), (1, "E002", "王五"), (1, "E003", "停用员工")]
    assert objectives == [(1, "E001")]
    assert records == [
        (1, "E001", "SELF_PENDING", None),
        (1, "E002", "SELF_PENDING", None),
        (2, "H001", "FINAL_CONFIRMED", "历史"),
    ]
    assert logs == [(2, 21, "历史")]


def test_reset_current_cycle_reviews_does_nothing_without_active_cycle(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"
    with connect(db_path, KEY) as connection:
        create_schema(connection)
        connection.execute("insert into evaluation_cycle (id, cycle_name, status) values (1, '2026-Q1', 'CLOSED')")
        connection.execute("insert into evaluation_record (id, cycle_id, emp_id, status) values (21, 1, 'H001', 'FINAL_CONFIRMED')")
        connection.commit()

    result = reset_current_cycle_reviews(db_path, KEY)

    assert result["cycle_id"] is None
    assert result["deleted_evaluation_records"] == 0
    assert result["deleted_adjustment_logs"] == 0
    assert result["created_evaluation_records"] == 0
    assert result["backup_path"] is None
    with connect(db_path, KEY) as connection:
        records = connection.execute("select id, cycle_id, emp_id, status from evaluation_record").fetchall()
    assert records == [(21, 1, "H001", "FINAL_CONFIRMED")]
