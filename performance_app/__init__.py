from __future__ import annotations

from pathlib import Path

from flask import Flask


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev-only-change-before-production",
        DATABASE=str(Path("data") / "performance_review.sqlite3"),
        EXPORT_DIR=str(Path("exports")),
        SEED_DEMO_DATA=True,
    )

    if test_config:
        app.config.update(test_config)
    if app.config.get("TESTING") and (not test_config or "SEED_DEMO_DATA" not in test_config):
        app.config["SEED_DEMO_DATA"] = False

    from performance_app import db
    from performance_app.routes import auth, cycles, employees, exports, health, objective, page_actions, pages, records, results, reviews

    db.init_app(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(cycles.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(records.bp)
    app.register_blueprint(reviews.bp)
    app.register_blueprint(objective.bp)
    app.register_blueprint(results.bp)
    app.register_blueprint(exports.bp)
    app.register_blueprint(pages.bp)
    app.register_blueprint(page_actions.bp)
    return app
