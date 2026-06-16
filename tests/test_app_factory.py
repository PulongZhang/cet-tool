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
