from __future__ import annotations

from pathlib import Path

from flask import Flask


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev-only-change-before-production",
        DATABASE=str(Path("data") / "performance_review.sqlite3"),
    )

    if test_config:
        app.config.update(test_config)

    from performance_app.routes import health

    app.register_blueprint(health.bp)
    return app
