import pytest

from performance_app import create_app


def test_create_app_returns_testable_flask_app():
    app = create_app({"TESTING": True, "DATABASE": ":memory:"})

    assert app.config["TESTING"] is True
    assert app.config["DATABASE"] == ":memory:"


def test_health_endpoint_returns_ok():
    app = create_app({"TESTING": True, "DATABASE": ":memory:"})
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_app_testing_mode_auto_fills_encryption_key(tmp_path):
    """TESTING 模式下,未显式传 DB_ENCRYPTION_KEY 时应自动填固定测试密钥。"""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "app.sqlite3")})
    assert app.config["DB_ENCRYPTION_KEY"]
    assert len(app.config["DB_ENCRYPTION_KEY"]) == 64  # 32 字节 hex


def test_create_app_non_testing_without_key_raises(tmp_path, monkeypatch):
    """非 TESTING 模式且环境变量缺失时,create_app 必须抛错。"""
    monkeypatch.delenv("DB_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DB_ENCRYPTION_KEY"):
        create_app({"DATABASE": str(tmp_path / "app.sqlite3")})


def test_create_app_non_testing_reads_env_key(tmp_path, monkeypatch):
    """非 TESTING 模式应从环境变量读密钥。"""
    monkeypatch.setenv("DB_ENCRYPTION_KEY", "c" * 64)
    app = create_app({"DATABASE": str(tmp_path / "app.sqlite3")})
    assert app.config["DB_ENCRYPTION_KEY"] == "c" * 64
