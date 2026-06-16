from performance_app import create_app


def make_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})


def assert_page_contains(client, path, expected_texts):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for text in expected_texts:
        assert text in html


def test_login_and_dashboard_pages_render(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    assert_page_contains(client, "/login", ["绩效考核评分工具", "用户名", "密码", "/auth/login"])
    assert_page_contains(client, "/", ["首页仪表盘", "我的自评", "结果导出"])


def test_workflow_role_pages_render_core_sections(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    assert_page_contains(client, "/self-review", ["我的自评", "工作总结", "self_score_1", "/records/my"])
    assert_page_contains(client, "/direct-reports", ["直接上级评分", "下属列表", "manager_score_1", "/records/direct-reports/submit"])
    assert_page_contains(client, "/reviews/indirect/page", ["间接上级审阅", "比例分布", "/reviews/indirect/submit"])
    assert_page_contains(client, "/reviews/dept-head/page", ["部门负责人确认", "比例分布", "/reviews/dept-head/submit"])


def test_hr_pages_render_import_results_and_export_controls(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    assert_page_contains(client, "/objective/import/page", ["客观数据导入", "objective.xlsx", "/objective/upload", "/objective/template"])
    assert_page_contains(client, "/results", ["计算结果总览", "执行计算", "最终确认", "/cycles/{cycle_id}/exports/final"])
