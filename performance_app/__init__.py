from __future__ import annotations

import os
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

    # 数据库加密密钥:生产从环境变量读;TESTING 模式自动用固定测试密钥(无需每个测试文件配置)
    if not app.config.get("DB_ENCRYPTION_KEY"):
        if app.config.get("TESTING"):
            app.config["DB_ENCRYPTION_KEY"] = "0" * 64
        else:
            env_key = os.environ.get("DB_ENCRYPTION_KEY")
            if not env_key:
                raise RuntimeError(
                    "未设置 DB_ENCRYPTION_KEY 环境变量。请运行 "
                    "`python -m performance_app.generate_key` 生成密钥,"
                    "再通过 DB_ENCRYPTION_KEY 环境变量提供(建议写入不入库的 .env)。"
                )
            app.config["DB_ENCRYPTION_KEY"] = env_key

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
