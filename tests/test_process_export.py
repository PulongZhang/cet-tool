from io import BytesIO

from openpyxl import load_workbook

from performance_app import create_app
from performance_app.db import connect
from performance_app.services.export_files import create_process_export


def make_app(tmp_path):
    return create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "app.sqlite3"),
        "EXPORT_DIR": str(tmp_path / "exports"),
    })


_SNAPSHOT_SQL = """
    insert into cycle_employee_snapshot
        (cycle_id, emp_id, emp_name, sequence, level, group_code, dept_name,
         dept_level_1, dept_level_2, dept_level_3, dept_level_4, post,
         direct_manager_id, indirect_manager_id, dept_head_id, active)
    values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
"""


def _create_cycle(app):
    key = app.config["DB_ENCRYPTION_KEY"]
    with connect(app.config["DATABASE"], key) as conn:
        conn.execute(
            "insert into evaluation_cycle (cycle_name, start_date, end_date, status, created_by) "
            "values ('2026-Q2', '2026-04-01', '2026-06-30', 'ACTIVE', 'hr')"
        )
        cycle_id = conn.execute("select id from evaluation_cycle").fetchone()[0]
        conn.commit()
    return cycle_id


def test_export_process_data_contains_objective_raw_values_and_dept_level(tmp_path):
    app = make_app(tmp_path)
    key = app.config["DB_ENCRYPTION_KEY"]
    cycle_id = _create_cycle(app)

    with connect(app.config["DATABASE"], key) as conn:
        conn.execute(
            _SNAPSHOT_SQL,
            (cycle_id, "E001", "张三", "员工序列", "P4", "EMPLOYEE_P4_10", "研发部",
             "研发部", None, None, "研发部", "工程师", "", "", ""),
        )
        conn.execute(
            "insert into evaluation_record (cycle_id, emp_id, status, current_subjective_level) "
            "values (?, 'E001', 'DEPT_CONFIRMED', 'A')",
            (cycle_id,),
        )
        conn.execute(
            """
            insert into objective_data
                (cycle_id, emp_id, diligence_raw_total, diligence_month_avg, diligence_level,
                 discipline_raw_count, discipline_level, learning_hours, learning_rank_pct, learning_level)
            values (?, 'E001', 180, 60, 'A', 3, 'A+', 12, 100, 'D')
            """,
            (cycle_id,),
        )
        conn.commit()

    with app.app_context():
        result = create_process_export(cycle_id, "hr001", "HR")

    client = app.test_client()
    download = client.get(result["download_url"])
    assert download.status_code == 200
    sheet = load_workbook(BytesIO(download.data)).active
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]

    assert rows[0] == [
        "工号", "姓名", "四级部门", "职级",
        "勤奋总量", "勤奋月均", "勤奋等级",
        "纪律异常次数", "纪律等级",
        "学习时长(h)", "学习排名%", "学习等级",
        "部门负责人评价",
    ]
    e001 = [r for r in rows[1:] if r[0] == "E001"][0]
    assert e001[1] == "张三"
    assert e001[2] == "研发部"   # 四级部门
    assert e001[3] == "P4"      # 职级
    assert e001[4] == 180       # 勤奋总量(原始值)
    assert e001[5] == 60        # 勤奋月均
    assert e001[6] == "A"       # 勤奋等级
    assert e001[7] == 3         # 纪律异常次数(原始值)
    assert e001[8] == "A+"      # 纪律等级
    assert e001[9] == 12        # 学习时长(原始值)
    assert e001[10] == 100      # 学习排名%
    assert e001[11] == "D"      # 学习等级
    assert e001[12] == "A"      # 部门负责人评价


def test_export_process_data_marks_missing_objective_with_dash(tmp_path):
    """没有客观数据 / 未到部门确认的员工,对应单元格显示 '-'。"""
    app = make_app(tmp_path)
    key = app.config["DB_ENCRYPTION_KEY"]
    cycle_id = _create_cycle(app)

    with connect(app.config["DATABASE"], key) as conn:
        conn.execute(
            _SNAPSHOT_SQL,
            (cycle_id, "E002", "李四", "员工序列", "P5", "EMPLOYEE_P5_10", "研发部",
             "研发部", None, None, "研发部", "", "", "", ""),
        )
        conn.execute(
            "insert into evaluation_record (cycle_id, emp_id, status) values (?, 'E002', 'SELF_PENDING')",
            (cycle_id,),
        )
        conn.commit()

    with app.app_context():
        result = create_process_export(cycle_id, "hr001", "HR")

    client = app.test_client()
    download = client.get(result["download_url"])
    sheet = load_workbook(BytesIO(download.data)).active
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    e002 = [r for r in rows[1:] if r[0] == "E002"][0]
    assert e002[4] == "-"    # 勤奋总量(无客观数据)
    assert e002[6] == "-"    # 勤奋等级
    assert e002[12] == "-"   # 部门负责人评价(未确认)


def test_export_process_button_downloads_xlsx_directly(tmp_path):
    """点'导出过程计算数据'按钮,POST 直接返回 xlsx 附件,不再需要二次下载链接。"""
    app = make_app(tmp_path)
    key = app.config["DB_ENCRYPTION_KEY"]
    client = app.test_client()
    client.post("/login", data={"username": "hr", "password": "admin123"})

    cycle_id = _create_cycle(app)
    with connect(app.config["DATABASE"], key) as conn:
        conn.execute(
            _SNAPSHOT_SQL,
            (cycle_id, "E001", "张三", "员工序列", "P4", "EMPLOYEE_P4_10", "研发部",
             "研发部", None, None, "研发部", "工程师", "", "", ""),
        )
        conn.execute(
            "insert into evaluation_record (cycle_id, emp_id, status, current_subjective_level) "
            "values (?, 'E001', 'DEPT_CONFIRMED', 'A')",
            (cycle_id,),
        )
        conn.execute(
            """
            insert into objective_data
                (cycle_id, emp_id, diligence_raw_total, diligence_month_avg, diligence_level,
                 discipline_raw_count, discipline_level, learning_hours, learning_rank_pct, learning_level)
            values (?, 'E001', 180, 60, 'A', 3, 'A+', 12, 100, 'D')
            """,
            (cycle_id,),
        )
        conn.commit()

    response = client.post("/page/export-process", data={"cycle_id": str(cycle_id)})

    assert response.status_code == 200
    assert "spreadsheet" in response.content_type
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert response.data[:2] == b"PK"  # xlsx 是 zip 文件,以 PK 开头
