# Performance Review Tool Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable slice of the quarterly performance review tool: Flask project skeleton, SQLite auto-initialization, core scoring rules, workflow state machine, data-scope permissions, and minimal cycle APIs.

**Architecture:** Use a Python Flask modular monolith with an application factory, SQLite as the V1 database, repository functions for database access, and pure domain modules for rules that must be easy to unit test. This plan intentionally implements the foundation first; employee Excel import, scoring pages, review pages, objective-data import, calculation result APIs, export files, and browser UI are separate follow-up plans built on this base.

**Tech Stack:** Python 3, Flask, SQLite, pytest, Werkzeug password hashing, standard-library `sqlite3`.

---

## Scope Check

The design spec covers multiple independent subsystems: authentication, cycle management, employee import, self review, manager scoring, indirect review, department-head confirmation, objective-data import, calculation, export, audit, and UI pages. This plan covers the first implementation slice that every later subsystem depends on:

1. Runtime and test harness.
2. SQLite database auto-creation and idempotent schema initialization.
3. Core grade, group, objective conversion, calculation, workflow, and permission rules.
4. Minimal cycle API and audit logging.

After this plan passes, create the next implementation plan for employee import and account bootstrapping.

## File Structure

- Create: `requirements.txt` — runtime Python dependencies.
- Create: `requirements-dev.txt` — test dependencies.
- Create: `.gitignore` — local Python, SQLite, and artifact ignores.
- Create: `performance_app/__init__.py` — Flask application factory.
- Create: `performance_app/routes/health.py` — health endpoint.
- Create: `performance_app/db.py` — SQLite connection and initialization helpers.
- Create: `performance_app/schema.sql` — SQLite schema and seed data.
- Create: `performance_app/domain/constants.py` — shared enum-like constants.
- Create: `performance_app/domain/employees.py` — employee group derivation.
- Create: `performance_app/domain/grades.py` — grade score and final-level mapping.
- Create: `performance_app/domain/objectives.py` — diligence, discipline, and learning conversion rules.
- Create: `performance_app/domain/calculation.py` — weighted score and ranking engine.
- Create: `performance_app/domain/workflow.py` — review-state transition rules.
- Create: `performance_app/domain/permissions.py` — record data-scope checks.
- Create: `performance_app/repositories/audit.py` — audit log writes.
- Create: `performance_app/repositories/cycles.py` — cycle persistence.
- Create: `performance_app/routes/cycles.py` — minimal cycle API.
- Create: `tests/` files listed per task.

---

### Task 1: Bootstrap Flask app and test harness

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `tests/test_app_factory.py`
- Create: `performance_app/__init__.py`
- Create: `performance_app/routes/__init__.py`
- Create: `performance_app/routes/health.py`

- [ ] **Step 1: Write dependency files and the failing app factory test**

Create `requirements.txt`:

```text
Flask==3.0.3
Werkzeug==3.0.3
```

Create `requirements-dev.txt`:

```text
-r requirements.txt
pytest==8.2.2
```

Create `.gitignore`:

```text
.venv/
__pycache__/
.pytest_cache/
*.pyc
*.sqlite3
*.db
/data/
/uploads/
/exports/
```

Create `tests/test_app_factory.py`:

```python
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
```

- [ ] **Step 2: Run the test and verify it fails because the app package does not exist**

Run:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_app_factory.py -q
```

Expected: `ModuleNotFoundError: No module named 'performance_app'`.

- [ ] **Step 3: Create the minimal Flask application factory and health route**

Create `performance_app/routes/__init__.py`:

```python
"""Route modules for the performance review tool."""
```

Create `performance_app/routes/health.py`:

```python
from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})
```

Create `performance_app/__init__.py`:

```python
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
```

- [ ] **Step 4: Run the app factory tests and verify they pass**

Run:

```bash
python -m pytest tests/test_app_factory.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the bootstrap**

Run:

```bash
git add .gitignore requirements.txt requirements-dev.txt performance_app tests/test_app_factory.py
git commit -m "feat: bootstrap Flask performance app"
```

---

### Task 2: Add SQLite auto-initialization and schema

**Files:**
- Create: `tests/test_database_initialization.py`
- Create: `performance_app/db.py`
- Create: `performance_app/schema.sql`
- Modify: `performance_app/__init__.py`

- [ ] **Step 1: Write failing SQLite initialization tests**

Create `tests/test_database_initialization.py`:

```python
import sqlite3

from performance_app import create_app


EXPECTED_TABLES = {
    "schema_version",
    "role_catalog",
    "user_account",
    "user_role",
    "evaluation_cycle",
    "cycle_employee_snapshot",
    "evaluation_record",
    "grade_adjustment_log",
    "objective_data",
    "import_batch",
    "import_error",
    "audit_log",
}


def table_names(db_path):
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    return {row[0] for row in rows}


def test_create_app_creates_sqlite_file_and_schema(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"

    create_app({"TESTING": True, "DATABASE": str(db_path)})

    assert db_path.exists()
    assert EXPECTED_TABLES.issubset(table_names(db_path))

    with sqlite3.connect(db_path) as connection:
        version = connection.execute(
            "select version from schema_version order by id desc limit 1"
        ).fetchone()[0]
        roles = {
            row[0]
            for row in connection.execute("select role_code from role_catalog").fetchall()
        }

    assert version == 1
    assert roles == {
        "EMPLOYEE",
        "DIRECT_MANAGER",
        "INDIRECT_MANAGER",
        "DEPT_HEAD",
        "HRBP",
        "ADMIN",
    }


def test_create_app_does_not_destroy_existing_database(tmp_path):
    db_path = tmp_path / "performance_review.sqlite3"
    create_app({"TESTING": True, "DATABASE": str(db_path)})

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            insert into evaluation_cycle
                (cycle_name, start_date, end_date, status, created_by, created_at)
            values
                ('2026-Q2', '2026-04-01', '2026-06-30', 'PREPARING', 'admin', '2026-06-16T00:00:00')
            """
        )
        connection.commit()

    create_app({"TESTING": True, "DATABASE": str(db_path)})

    with sqlite3.connect(db_path) as connection:
        count = connection.execute("select count(*) from evaluation_cycle").fetchone()[0]

    assert count == 1
```

- [ ] **Step 2: Run the database tests and verify they fail because initialization is missing**

Run:

```bash
python -m pytest tests/test_database_initialization.py -q
```

Expected: failure showing the SQLite file does not exist or expected tables are missing.

- [ ] **Step 3: Add SQLite initialization code and schema**

Create `performance_app/db.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

from flask import Flask, current_app, g

SCHEMA_VERSION = 1


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("pragma foreign_keys = on")
        g.db = connection
    return g.db


def close_db(error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def _connect_database(database_path: str) -> sqlite3.Connection:
    return sqlite3.connect(database_path)


def init_database(app: Flask) -> None:
    database_path = app.config["DATABASE"]
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    with _connect_database(database_path) as connection:
        connection.execute("pragma foreign_keys = on")
        connection.executescript(schema_path().read_text(encoding="utf-8"))
        row = connection.execute(
            "select version from schema_version order by id desc limit 1"
        ).fetchone()
        if row is None:
            connection.execute(
                "insert into schema_version (version, applied_at) values (?, datetime('now'))",
                (SCHEMA_VERSION,),
            )
        elif row[0] > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {row[0]} is newer than application version {SCHEMA_VERSION}"
            )
        connection.commit()


def init_app(app: Flask) -> None:
    init_database(app)
    app.teardown_appcontext(close_db)
```

Create `performance_app/schema.sql`:

```sql
create table if not exists schema_version (
    id integer primary key autoincrement,
    version integer not null,
    applied_at text not null
);

create table if not exists role_catalog (
    role_code text primary key,
    role_name text not null
);

insert or ignore into role_catalog (role_code, role_name) values
    ('EMPLOYEE', '被考核员工'),
    ('DIRECT_MANAGER', '直接上级'),
    ('INDIRECT_MANAGER', '间接上级'),
    ('DEPT_HEAD', '部门负责人'),
    ('HRBP', 'HR 数据处理员'),
    ('ADMIN', '管理员');

create table if not exists user_account (
    id integer primary key autoincrement,
    emp_id text unique not null,
    username text unique not null,
    password_hash text not null,
    status text not null default 'ACTIVE',
    last_login_at text,
    created_at text not null default (datetime('now'))
);

create table if not exists user_role (
    id integer primary key autoincrement,
    user_id integer not null references user_account(id),
    role_code text not null references role_catalog(role_code),
    unique(user_id, role_code)
);

create table if not exists evaluation_cycle (
    id integer primary key autoincrement,
    cycle_name text unique not null,
    start_date text not null,
    end_date text not null,
    status text not null default 'PREPARING',
    created_by text not null,
    created_at text not null default (datetime('now'))
);

create table if not exists cycle_employee_snapshot (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id) on delete cascade,
    emp_id text not null,
    emp_name text not null,
    sequence text not null,
    level text not null,
    group_code text not null,
    dept_name text not null,
    direct_manager_id text not null,
    indirect_manager_id text not null,
    dept_head_id text not null,
    active integer not null default 1,
    unique(cycle_id, emp_id)
);

create table if not exists evaluation_record (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id) on delete cascade,
    emp_id text not null,
    status text not null default 'SELF_PENDING',
    self_summary text,
    self_score_1 text,
    self_score_2 text,
    self_score_3 text,
    manager_score_1 text,
    manager_score_2 text,
    manager_score_3 text,
    manager_comment text,
    initial_total_grade text,
    current_subjective_level text,
    final_subjective_grade_1 text,
    final_subjective_grade_2 text,
    final_subjective_grade_3 text,
    suggested_subjective_level text,
    weighted_score real,
    rank_in_group integer,
    rank_total integer,
    suggested_level text,
    final_level text,
    special_reason text,
    self_skipped_due_to_timeout integer not null default 0,
    submitted_at text,
    updated_at text not null default (datetime('now')),
    unique(cycle_id, emp_id)
);

create table if not exists grade_adjustment_log (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id),
    record_id integer not null references evaluation_record(id),
    stage text not null,
    adjustment_type text not null,
    field_name text not null,
    before_value text,
    after_value text,
    reason text not null,
    operator_id text not null,
    operator_name text not null,
    adjusted_at text not null default (datetime('now'))
);

create table if not exists objective_data (
    id integer primary key autoincrement,
    cycle_id integer not null references evaluation_cycle(id) on delete cascade,
    emp_id text not null,
    diligence_raw_total real not null,
    diligence_month_avg real not null,
    diligence_level text not null,
    discipline_raw_count integer not null,
    discipline_level text not null,
    learning_hours real not null,
    learning_rank_pct real,
    learning_level text,
    corrected integer not null default 0,
    correction_reason text,
    updated_at text not null default (datetime('now')),
    unique(cycle_id, emp_id)
);

create table if not exists import_batch (
    id integer primary key autoincrement,
    cycle_id integer references evaluation_cycle(id),
    import_type text not null,
    file_name text not null,
    total_count integer not null default 0,
    success_count integer not null default 0,
    failed_count integer not null default 0,
    operator_id text not null,
    imported_at text not null default (datetime('now'))
);

create table if not exists import_error (
    id integer primary key autoincrement,
    batch_id integer not null references import_batch(id) on delete cascade,
    row_number integer not null,
    emp_id text,
    field_name text not null,
    error_message text not null,
    raw_data text not null
);

create table if not exists audit_log (
    id integer primary key autoincrement,
    cycle_id integer,
    operator_id text not null,
    operator_name text not null,
    action text not null,
    target_type text not null,
    target_id text not null,
    before_snapshot text,
    after_snapshot text,
    reason text,
    ip_address text,
    user_agent text,
    created_at text not null default (datetime('now'))
);

create index if not exists idx_record_cycle_status on evaluation_record(cycle_id, status);
create index if not exists idx_snapshot_direct_manager on cycle_employee_snapshot(cycle_id, direct_manager_id);
create index if not exists idx_snapshot_indirect_manager on cycle_employee_snapshot(cycle_id, indirect_manager_id);
create index if not exists idx_snapshot_dept_head on cycle_employee_snapshot(cycle_id, dept_head_id);
create index if not exists idx_audit_target on audit_log(target_type, target_id);
```

Modify `performance_app/__init__.py`:

```python
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

    from performance_app import db
    from performance_app.routes import health

    db.init_app(app)
    app.register_blueprint(health.bp)
    return app
```

- [ ] **Step 4: Run database tests and app factory tests**

Run:

```bash
python -m pytest tests/test_database_initialization.py tests/test_app_factory.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit SQLite initialization**

Run:

```bash
git add performance_app tests/test_database_initialization.py
git commit -m "feat: initialize SQLite schema on app startup"
```

---

### Task 3: Add grade, group, and objective conversion rules

**Files:**
- Create: `tests/test_domain_rules.py`
- Create: `performance_app/domain/__init__.py`
- Create: `performance_app/domain/constants.py`
- Create: `performance_app/domain/employees.py`
- Create: `performance_app/domain/grades.py`
- Create: `performance_app/domain/objectives.py`

- [ ] **Step 1: Write failing tests for spec rules**

Create `tests/test_domain_rules.py`:

```python
import pytest

from performance_app.domain.employees import derive_group_code
from performance_app.domain.grades import final_level_from_rank_pct, grade_to_score
from performance_app.domain.objectives import (
    diligence_level_from_quarter_total,
    discipline_level_from_exception_count,
    learning_level_from_rank_pct,
)


def test_derive_group_code_uses_specific_p_level():
    assert derive_group_code("管理序列", "不适用") == "MANAGEMENT"
    assert derive_group_code("员工序列", "P1") == "EMPLOYEE_P1_3"
    assert derive_group_code("员工序列", "P3") == "EMPLOYEE_P1_3"
    assert derive_group_code("员工序列", "P4") == "EMPLOYEE_P4_10"
    assert derive_group_code("员工序列", "P10") == "EMPLOYEE_P4_10"


def test_derive_group_code_rejects_invalid_employee_level():
    with pytest.raises(ValueError, match="Unsupported employee level"):
        derive_group_code("员工序列", "P11")


def test_grade_to_score_mapping_matches_spec():
    assert grade_to_score("A+") == 100
    assert grade_to_score("A") == 93
    assert grade_to_score("B+") == 86
    assert grade_to_score("B") == 80
    assert grade_to_score("B-") == 70
    assert grade_to_score("C") == 60
    assert grade_to_score("D") == 50


def test_final_level_from_rank_pct_matches_spec_boundaries():
    assert final_level_from_rank_pct(5) == "A+"
    assert final_level_from_rank_pct(20) == "A"
    assert final_level_from_rank_pct(50) == "B+"
    assert final_level_from_rank_pct(85) == "B"
    assert final_level_from_rank_pct(95) == "B-"
    assert final_level_from_rank_pct(98) == "C"
    assert final_level_from_rank_pct(99) == "D"


def test_diligence_level_uses_month_average_from_quarter_total():
    assert diligence_level_from_quarter_total(30) == "D"
    assert diligence_level_from_quarter_total(33) == "C"
    assert diligence_level_from_quarter_total(120) == "B"
    assert diligence_level_from_quarter_total(180) == "A"


def test_discipline_level_uses_total_exception_count():
    assert discipline_level_from_exception_count(3) == "A+"
    assert discipline_level_from_exception_count(6) == "A"
    assert discipline_level_from_exception_count(9) == "B"
    assert discipline_level_from_exception_count(12) == "C"
    assert discipline_level_from_exception_count(13) == "D"


def test_learning_level_uses_rank_percent_boundaries():
    assert learning_level_from_rank_pct(5) == "A+"
    assert learning_level_from_rank_pct(20) == "A"
    assert learning_level_from_rank_pct(50) == "B+"
    assert learning_level_from_rank_pct(85) == "B"
    assert learning_level_from_rank_pct(95) == "B-"
    assert learning_level_from_rank_pct(98) == "C"
    assert learning_level_from_rank_pct(100) == "D"
```

- [ ] **Step 2: Run the tests and verify they fail because domain modules are missing**

Run:

```bash
python -m pytest tests/test_domain_rules.py -q
```

Expected: `ModuleNotFoundError` for `performance_app.domain`.

- [ ] **Step 3: Implement the domain rule modules**

Create `performance_app/domain/__init__.py`:

```python
"""Pure domain rules for the performance review tool."""
```

Create `performance_app/domain/constants.py`:

```python
GRADES = ("A+", "A", "B+", "B", "B-", "C", "D")

GRADE_SCORES = {
    "A+": 100,
    "A": 93,
    "B+": 86,
    "B": 80,
    "B-": 70,
    "C": 60,
    "D": 50,
}

GROUP_MANAGEMENT = "MANAGEMENT"
GROUP_EMPLOYEE_P1_3 = "EMPLOYEE_P1_3"
GROUP_EMPLOYEE_P4_10 = "EMPLOYEE_P4_10"

EMPLOYEE_LEVELS_P1_3 = {"P1", "P2", "P3"}
EMPLOYEE_LEVELS_P4_10 = {"P4", "P5", "P6", "P7", "P8", "P9", "P10"}

SEQUENCE_MANAGEMENT = "管理序列"
SEQUENCE_EMPLOYEE = "员工序列"
```

Create `performance_app/domain/employees.py`:

```python
from performance_app.domain.constants import (
    EMPLOYEE_LEVELS_P1_3,
    EMPLOYEE_LEVELS_P4_10,
    GROUP_EMPLOYEE_P1_3,
    GROUP_EMPLOYEE_P4_10,
    GROUP_MANAGEMENT,
    SEQUENCE_EMPLOYEE,
    SEQUENCE_MANAGEMENT,
)


def derive_group_code(sequence: str, level: str) -> str:
    normalized_sequence = sequence.strip()
    normalized_level = level.strip().upper()

    if normalized_sequence == SEQUENCE_MANAGEMENT:
        return GROUP_MANAGEMENT

    if normalized_sequence != SEQUENCE_EMPLOYEE:
        raise ValueError(f"Unsupported sequence: {sequence}")

    if normalized_level in EMPLOYEE_LEVELS_P1_3:
        return GROUP_EMPLOYEE_P1_3

    if normalized_level in EMPLOYEE_LEVELS_P4_10:
        return GROUP_EMPLOYEE_P4_10

    raise ValueError(f"Unsupported employee level: {level}")
```

Create `performance_app/domain/grades.py`:

```python
from performance_app.domain.constants import GRADE_SCORES


def grade_to_score(grade: str) -> int:
    try:
        return GRADE_SCORES[grade]
    except KeyError as exc:
        raise ValueError(f"Unsupported grade: {grade}") from exc


def final_level_from_rank_pct(rank_pct: float) -> str:
    if rank_pct <= 5:
        return "A+"
    if rank_pct <= 20:
        return "A"
    if rank_pct <= 50:
        return "B+"
    if rank_pct <= 85:
        return "B"
    if rank_pct <= 95:
        return "B-"
    if rank_pct <= 98:
        return "C"
    return "D"
```

Create `performance_app/domain/objectives.py`:

```python
from performance_app.domain.grades import final_level_from_rank_pct


def diligence_level_from_quarter_total(quarter_total: float) -> str:
    if quarter_total < 0:
        raise ValueError("Diligence total cannot be negative")

    month_average = quarter_total / 3
    if month_average < 11:
        return "D"
    if month_average < 40:
        return "C"
    if month_average < 60:
        return "B"
    return "A"


def discipline_level_from_exception_count(exception_count: int) -> str:
    if exception_count < 0:
        raise ValueError("Exception count cannot be negative")

    if exception_count <= 3:
        return "A+"
    if exception_count <= 6:
        return "A"
    if exception_count <= 9:
        return "B"
    if exception_count <= 12:
        return "C"
    return "D"


def learning_level_from_rank_pct(rank_pct: float) -> str:
    return final_level_from_rank_pct(rank_pct)
```

- [ ] **Step 4: Run domain rule tests**

Run:

```bash
python -m pytest tests/test_domain_rules.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit domain rules**

Run:

```bash
git add performance_app/domain tests/test_domain_rules.py
git commit -m "feat: add performance grading domain rules"
```

---

### Task 4: Add calculation engine

**Files:**
- Create: `tests/test_calculation_engine.py`
- Create: `performance_app/domain/calculation.py`

- [ ] **Step 1: Write failing calculation tests**

Create `tests/test_calculation_engine.py`:

```python
from performance_app.domain.calculation import calculate_weighted_score, rank_records


def test_calculate_weighted_score_for_employee_p4_10():
    result = calculate_weighted_score(
        group_code="EMPLOYEE_P4_10",
        subjective_1="A",
        subjective_2="A",
        subjective_3="B+",
        diligence="A",
        discipline="B",
        learning="B+",
    )

    assert result.weighted_score == 89.9
    assert result.contributions == {
        "subjective_1": 27.9,
        "subjective_2": 23.2,
        "subjective_3": 25.8,
        "diligence": 4.7,
        "discipline": 4.0,
        "learning": 4.3,
    }


def test_calculate_weighted_score_for_management():
    result = calculate_weighted_score(
        group_code="MANAGEMENT",
        subjective_1="A",
        subjective_2="B+",
        subjective_3="B+",
        diligence="A",
        discipline="A+",
        learning="A",
    )

    assert result.weighted_score == 88.6


def test_rank_records_sorts_by_group_score_and_emp_id():
    ranked = rank_records(
        [
            {"record_id": 1, "emp_id": "E002", "group_code": "EMPLOYEE_P1_3", "weighted_score": 90.0},
            {"record_id": 2, "emp_id": "E001", "group_code": "EMPLOYEE_P1_3", "weighted_score": 90.0},
            {"record_id": 3, "emp_id": "E003", "group_code": "EMPLOYEE_P4_10", "weighted_score": 95.0},
        ]
    )

    assert ranked == [
        {
            "record_id": 2,
            "emp_id": "E001",
            "group_code": "EMPLOYEE_P1_3",
            "weighted_score": 90.0,
            "rank_in_group": 1,
            "rank_total": 2,
            "rank_pct": 50.0,
            "suggested_level": "B+",
        },
        {
            "record_id": 1,
            "emp_id": "E002",
            "group_code": "EMPLOYEE_P1_3",
            "weighted_score": 90.0,
            "rank_in_group": 2,
            "rank_total": 2,
            "rank_pct": 100.0,
            "suggested_level": "D",
        },
        {
            "record_id": 3,
            "emp_id": "E003",
            "group_code": "EMPLOYEE_P4_10",
            "weighted_score": 95.0,
            "rank_in_group": 1,
            "rank_total": 1,
            "rank_pct": 100.0,
            "suggested_level": "D",
        },
    ]
```

- [ ] **Step 2: Run calculation tests and verify they fail because the module is missing**

Run:

```bash
python -m pytest tests/test_calculation_engine.py -q
```

Expected: `ModuleNotFoundError` or `ImportError` for `performance_app.domain.calculation`.

- [ ] **Step 3: Implement calculation engine**

Create `performance_app/domain/calculation.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from operator import itemgetter

from performance_app.domain.grades import final_level_from_rank_pct, grade_to_score

WEIGHTS = {
    "MANAGEMENT": {
        "subjective_1": 0.20,
        "subjective_2": 0.30,
        "subjective_3": 0.30,
        "diligence": 0.10,
        "discipline": 0.05,
        "learning": 0.05,
    },
    "EMPLOYEE_P4_10": {
        "subjective_1": 0.30,
        "subjective_2": 0.25,
        "subjective_3": 0.30,
        "diligence": 0.05,
        "discipline": 0.05,
        "learning": 0.05,
    },
    "EMPLOYEE_P1_3": {
        "subjective_1": 0.30,
        "subjective_2": 0.20,
        "subjective_3": 0.30,
        "diligence": 0.10,
        "discipline": 0.05,
        "learning": 0.05,
    },
}


@dataclass(frozen=True)
class WeightedScoreResult:
    weighted_score: float
    contributions: dict[str, float]


def calculate_weighted_score(
    *,
    group_code: str,
    subjective_1: str,
    subjective_2: str,
    subjective_3: str,
    diligence: str,
    discipline: str,
    learning: str,
) -> WeightedScoreResult:
    if group_code not in WEIGHTS:
        raise ValueError(f"Unsupported group code: {group_code}")

    weights = WEIGHTS[group_code]
    grades = {
        "subjective_1": subjective_1,
        "subjective_2": subjective_2,
        "subjective_3": subjective_3,
        "diligence": diligence,
        "discipline": discipline,
        "learning": learning,
    }
    contributions = {
        key: round(grade_to_score(value) * weights[key], 1)
        for key, value in grades.items()
    }
    return WeightedScoreResult(
        weighted_score=round(sum(contributions.values()), 1),
        contributions=contributions,
    )


def rank_records(records: list[dict]) -> list[dict]:
    sorted_records = sorted(
        records,
        key=lambda item: (item["group_code"], -item["weighted_score"], item["emp_id"]),
    )
    ranked: list[dict] = []

    for group_code, group_items in groupby(sorted_records, key=itemgetter("group_code")):
        group = list(group_items)
        total = len(group)
        for index, item in enumerate(group, start=1):
            rank_pct = round(index / total * 100, 1)
            ranked.append(
                {
                    **item,
                    "rank_in_group": index,
                    "rank_total": total,
                    "rank_pct": rank_pct,
                    "suggested_level": final_level_from_rank_pct(rank_pct),
                }
            )

    return ranked
```

- [ ] **Step 4: Run calculation tests and full domain tests**

Run:

```bash
python -m pytest tests/test_calculation_engine.py tests/test_domain_rules.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit calculation engine**

Run:

```bash
git add performance_app/domain/calculation.py tests/test_calculation_engine.py
git commit -m "feat: add weighted calculation engine"
```

---

### Task 5: Add workflow state machine and permission checks

**Files:**
- Create: `tests/test_workflow_permissions.py`
- Create: `performance_app/domain/workflow.py`
- Create: `performance_app/domain/permissions.py`

- [ ] **Step 1: Write failing tests for workflow and data scope**

Create `tests/test_workflow_permissions.py`:

```python
import pytest

from performance_app.domain.permissions import can_view_record
from performance_app.domain.workflow import next_status, withdraw_status


def test_next_status_allows_core_review_flow():
    assert next_status("SELF_PENDING", "save_self_draft") == "SELF_DRAFT"
    assert next_status("SELF_DRAFT", "submit_self") == "DIRECT_PENDING"
    assert next_status("DIRECT_PENDING", "submit_manager") == "INDIRECT_PENDING"
    assert next_status("INDIRECT_PENDING", "submit_indirect") == "DEPT_HEAD_PENDING"
    assert next_status("DEPT_HEAD_PENDING", "submit_dept_head") == "HR_PENDING"
    assert next_status("HR_PENDING", "calculate") == "COMPLETED"


def test_next_status_rejects_invalid_transition():
    with pytest.raises(ValueError, match="Invalid transition"):
        next_status("SELF_PENDING", "submit_manager")


def test_withdraw_status_matches_spec_matrix():
    assert withdraw_status("DIRECT_PENDING") == "SELF_DRAFT"
    assert withdraw_status("INDIRECT_PENDING") == "DIRECT_DRAFT"
    assert withdraw_status("DEPT_HEAD_PENDING") == "INDIRECT_PENDING"
    assert withdraw_status("HR_PENDING") == "DEPT_HEAD_PENDING"
    assert withdraw_status("COMPLETED") == "COMPLETED"


def test_can_view_record_uses_roles_and_data_scope():
    record = {
        "emp_id": "E001",
        "direct_manager_id": "M001",
        "indirect_manager_id": "M002",
        "dept_head_id": "M003",
    }

    assert can_view_record({"emp_id": "E001", "roles": ["EMPLOYEE"]}, record)
    assert can_view_record({"emp_id": "M001", "roles": ["DIRECT_MANAGER"]}, record)
    assert can_view_record({"emp_id": "M002", "roles": ["INDIRECT_MANAGER"]}, record)
    assert can_view_record({"emp_id": "M003", "roles": ["DEPT_HEAD"]}, record)
    assert can_view_record({"emp_id": "HR001", "roles": ["HRBP"]}, record)
    assert can_view_record({"emp_id": "ADMIN001", "roles": ["ADMIN"]}, record)
    assert not can_view_record({"emp_id": "E999", "roles": ["EMPLOYEE"]}, record)
```

- [ ] **Step 2: Run tests and verify they fail because modules are missing**

Run:

```bash
python -m pytest tests/test_workflow_permissions.py -q
```

Expected: `ModuleNotFoundError` or `ImportError` for workflow or permission modules.

- [ ] **Step 3: Implement workflow and permission functions**

Create `performance_app/domain/workflow.py`:

```python
TRANSITIONS = {
    ("SELF_PENDING", "save_self_draft"): "SELF_DRAFT",
    ("SELF_DRAFT", "save_self_draft"): "SELF_DRAFT",
    ("SELF_PENDING", "submit_self"): "DIRECT_PENDING",
    ("SELF_DRAFT", "submit_self"): "DIRECT_PENDING",
    ("DIRECT_PENDING", "save_manager_draft"): "DIRECT_DRAFT",
    ("DIRECT_DRAFT", "save_manager_draft"): "DIRECT_DRAFT",
    ("DIRECT_PENDING", "submit_manager"): "INDIRECT_PENDING",
    ("DIRECT_DRAFT", "submit_manager"): "INDIRECT_PENDING",
    ("INDIRECT_PENDING", "submit_indirect"): "DEPT_HEAD_PENDING",
    ("DEPT_HEAD_PENDING", "submit_dept_head"): "HR_PENDING",
    ("HR_PENDING", "calculate"): "COMPLETED",
}

WITHDRAW_TARGETS = {
    "DIRECT_PENDING": "SELF_DRAFT",
    "INDIRECT_PENDING": "DIRECT_DRAFT",
    "DEPT_HEAD_PENDING": "INDIRECT_PENDING",
    "HR_PENDING": "DEPT_HEAD_PENDING",
    "COMPLETED": "COMPLETED",
}


def next_status(current_status: str, action: str) -> str:
    key = (current_status, action)
    if key not in TRANSITIONS:
        raise ValueError(f"Invalid transition: {current_status} via {action}")
    return TRANSITIONS[key]


def withdraw_status(current_status: str) -> str:
    if current_status not in WITHDRAW_TARGETS:
        raise ValueError(f"Cannot withdraw from status: {current_status}")
    return WITHDRAW_TARGETS[current_status]
```

Create `performance_app/domain/permissions.py`:

```python
def can_view_record(user: dict, record: dict) -> bool:
    roles = set(user.get("roles", []))
    emp_id = user.get("emp_id")

    if "HRBP" in roles or "ADMIN" in roles:
        return True
    if "EMPLOYEE" in roles and record.get("emp_id") == emp_id:
        return True
    if "DIRECT_MANAGER" in roles and record.get("direct_manager_id") == emp_id:
        return True
    if "INDIRECT_MANAGER" in roles and record.get("indirect_manager_id") == emp_id:
        return True
    if "DEPT_HEAD" in roles and record.get("dept_head_id") == emp_id:
        return True
    return False
```

- [ ] **Step 4: Run workflow and permission tests**

Run:

```bash
python -m pytest tests/test_workflow_permissions.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit workflow and permission rules**

Run:

```bash
git add performance_app/domain/workflow.py performance_app/domain/permissions.py tests/test_workflow_permissions.py
git commit -m "feat: add workflow and permission rules"
```

---

### Task 6: Add minimal cycle repository and API

**Files:**
- Create: `tests/test_cycle_api.py`
- Create: `performance_app/repositories/__init__.py`
- Create: `performance_app/repositories/audit.py`
- Create: `performance_app/repositories/cycles.py`
- Create: `performance_app/routes/cycles.py`
- Modify: `performance_app/__init__.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_cycle_api.py`:

```python
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
```

- [ ] **Step 2: Run API tests and verify they fail because routes are missing**

Run:

```bash
python -m pytest tests/test_cycle_api.py -q
```

Expected: failures with 404 responses for `/cycles` or missing repository modules.

- [ ] **Step 3: Implement audit and cycle repositories**

Create `performance_app/repositories/__init__.py`:

```python
"""Persistence helpers for the performance review tool."""
```

Create `performance_app/repositories/audit.py`:

```python
from __future__ import annotations

import json
from typing import Any

from performance_app.db import get_db


def write_audit_log(
    *,
    action: str,
    target_type: str,
    target_id: str | int,
    operator_id: str,
    operator_name: str,
    cycle_id: int | None = None,
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    get_db().execute(
        """
        insert into audit_log
            (cycle_id, operator_id, operator_name, action, target_type, target_id,
             before_snapshot, after_snapshot, reason, ip_address, user_agent)
        values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cycle_id,
            operator_id,
            operator_name,
            action,
            target_type,
            str(target_id),
            json.dumps(before_snapshot, ensure_ascii=False) if before_snapshot else None,
            json.dumps(after_snapshot, ensure_ascii=False) if after_snapshot else None,
            reason,
            ip_address,
            user_agent,
        ),
    )
```

Create `performance_app/repositories/cycles.py`:

```python
from __future__ import annotations

from sqlite3 import IntegrityError, Row

from performance_app.db import get_db


def row_to_cycle(row: Row) -> dict:
    return {
        "id": row["id"],
        "cycle_name": row["cycle_name"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "status": row["status"],
        "created_by": row["created_by"],
    }


def list_cycles() -> list[dict]:
    rows = get_db().execute(
        """
        select id, cycle_name, start_date, end_date, status, created_by
        from evaluation_cycle
        order by id desc
        """
    ).fetchall()
    return [row_to_cycle(row) for row in rows]


def get_cycle(cycle_id: int) -> dict | None:
    row = get_db().execute(
        """
        select id, cycle_name, start_date, end_date, status, created_by
        from evaluation_cycle
        where id = ?
        """,
        (cycle_id,),
    ).fetchone()
    return row_to_cycle(row) if row else None


def create_cycle(cycle_name: str, start_date: str, end_date: str, created_by: str) -> dict:
    try:
        cursor = get_db().execute(
            """
            insert into evaluation_cycle
                (cycle_name, start_date, end_date, status, created_by)
            values
                (?, ?, ?, 'PREPARING', ?)
            """,
            (cycle_name, start_date, end_date, created_by),
        )
    except IntegrityError as exc:
        raise ValueError(f"cycle already exists: {cycle_name}") from exc
    return get_cycle(cursor.lastrowid)


def has_active_cycle(excluding_cycle_id: int | None = None) -> bool:
    if excluding_cycle_id is None:
        row = get_db().execute(
            "select id from evaluation_cycle where status = 'ACTIVE' limit 1"
        ).fetchone()
    else:
        row = get_db().execute(
            "select id from evaluation_cycle where status = 'ACTIVE' and id != ? limit 1",
            (excluding_cycle_id,),
        ).fetchone()
    return row is not None


def update_cycle_status(cycle_id: int, expected_status: str, new_status: str) -> dict | None:
    cursor = get_db().execute(
        """
        update evaluation_cycle
        set status = ?
        where id = ? and status = ?
        """,
        (new_status, cycle_id, expected_status),
    )
    if cursor.rowcount == 0:
        return None
    return get_cycle(cycle_id)
```

- [ ] **Step 4: Implement cycle routes and register them**

Create `performance_app/routes/cycles.py`:

```python
from __future__ import annotations

from flask import Blueprint, jsonify, request

from performance_app.db import get_db
from performance_app.repositories.audit import write_audit_log
from performance_app.repositories.cycles import (
    create_cycle,
    has_active_cycle,
    list_cycles,
    update_cycle_status,
)

bp = Blueprint("cycles", __name__)


def operator() -> tuple[str, str]:
    return (
        request.headers.get("X-Operator-Id", "system"),
        request.headers.get("X-Operator-Name", "系统"),
    )


@bp.get("/cycles")
def cycles_index():
    return jsonify({"cycles": list_cycles()})


@bp.post("/cycles")
def cycles_create():
    payload = request.get_json(silent=True) or {}
    cycle_name = payload.get("cycle_name")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")

    if not cycle_name or not start_date or not end_date:
        return jsonify({"error": "cycle_name, start_date, and end_date are required"}), 400

    operator_id, operator_name = operator()
    try:
        cycle = create_cycle(cycle_name, start_date, end_date, operator_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    write_audit_log(
        action="CREATE_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle["id"],
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle["id"],
        after_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"cycle": cycle}), 201


@bp.post("/cycles/<int:cycle_id>/start")
def cycles_start(cycle_id: int):
    if has_active_cycle(excluding_cycle_id=cycle_id):
        return jsonify({"error": "another ACTIVE cycle already exists"}), 409

    cycle = update_cycle_status(cycle_id, "PREPARING", "ACTIVE")
    if cycle is None:
        return jsonify({"error": "cycle is not PREPARING or does not exist"}), 409

    operator_id, operator_name = operator()
    write_audit_log(
        action="START_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"cycle": cycle})


@bp.post("/cycles/<int:cycle_id>/close")
def cycles_close(cycle_id: int):
    cycle = update_cycle_status(cycle_id, "ACTIVE", "CLOSED")
    if cycle is None:
        return jsonify({"error": "cycle is not ACTIVE or does not exist"}), 409

    operator_id, operator_name = operator()
    write_audit_log(
        action="CLOSE_CYCLE",
        target_type="evaluation_cycle",
        target_id=cycle_id,
        operator_id=operator_id,
        operator_name=operator_name,
        cycle_id=cycle_id,
        after_snapshot=cycle,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    get_db().commit()
    return jsonify({"cycle": cycle})
```

Modify `performance_app/__init__.py`:

```python
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

    from performance_app import db
    from performance_app.routes import cycles, health

    db.init_app(app)
    app.register_blueprint(health.bp)
    app.register_blueprint(cycles.bp)
    return app
```

- [ ] **Step 5: Run cycle API tests and full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit cycle API**

Run:

```bash
git add performance_app tests/test_cycle_api.py
git commit -m "feat: add cycle API and audit logging"
```

---

### Task 7: Add local run documentation and final verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write run instructions**

Create `README.md`:

```markdown
# 季度绩效考核评分工具

这是按 `docs/superpowers/specs/2026-06-16-performance-review-tool-design.md` 实现的 Flask + SQLite V1 工具。

## 本地启动

```bash
python -m pip install -r requirements-dev.txt
python -m flask --app performance_app run --debug
```

启动时应用会读取 `DATABASE` 配置。默认数据库路径为 `data/performance_review.sqlite3`。如果数据库文件不存在，应用会自动创建父目录、SQLite 文件、业务表、索引、角色初始数据和 `schema_version` 记录；如果文件已存在，启动过程不会清空已有业务数据。

## 测试

```bash
python -m pytest -q
```

## 当前实现范围

- Flask 应用工厂。
- SQLite 自动初始化和幂等建表。
- 角色、周期、人员快照、考核记录、调整、客观数据、导入错误和审计日志基础表。
- 评分等级、计算分组、客观数据转换、加权计算、排名定级、状态流转和数据范围判断。
- 周期创建、列表、启动、关闭 API。

员工导入、账号初始化、评分流、审阅、客观数据导入、计算结果、Excel 导出和页面实现按后续计划继续推进。
```

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
git status --short
```

Expected:

```text
... passed
 M README.md
```

Only `README.md` should be uncommitted at this point.

- [ ] **Step 3: Commit README**

Run:

```bash
git add README.md
git commit -m "docs: add local run instructions"
```

- [ ] **Step 4: Verify final repository state**

Run:

```bash
python -m pytest -q
git status --short --branch
git log --oneline -5
```

Expected:

```text
... passed
## master
<latest> docs: add local run instructions
<previous> feat: add cycle API and audit logging
```

---

## Self-Review Notes

- Spec coverage in this plan: Flask/SQLite technology selection, SQLite auto-create schema, schema versioning, core data tables, grade mapping, objective conversion, weighted calculation, ranking, state transitions, data-scope permission checks, cycle lifecycle basics, and audit logging.
- Explicitly not covered in this plan: Excel import/export, account creation from imported employees, login/session flow, self-review APIs, manager scoring APIs, indirect/department review APIs, objective-data import APIs, final result APIs, and UI pages. These are separate subsystems and need their own implementation plans after this foundation passes.
- Placeholder scan: this plan contains concrete files, commands, expected results, and code blocks for every implementation step in scope.
- Type consistency: status values, role codes, group codes, table names, and endpoint paths match the design spec sections cited by this plan.
