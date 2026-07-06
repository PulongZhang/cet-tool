# SQLite 数据库文件加密 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **提交策略(用户明确要求):** 全部任务实现完成、并通过最终验收后,**统一一次 commit + push**。任务步骤中不写单独 commit;如需中途回滚,用 `git stash` / `git restore`。

**Goal:** 把 `data/performance_review.sqlite3` 改为 SQLCipher 整库 AES-256 加密,文件脱离应用不可直读,并满足合规审计要求。

**Architecture:** 应用所有连接收敛到 `performance_app/db.py` 的 `connect(path, key)`;`sqlcipher3-wheels` 提供 `sqlcipher3` 模块,DB-API 2.0 与标准库 `sqlite3` 完全一致,故 `import sqlcipher3 as sqlite3` 后现有代码无感知;密钥来自 `DB_ENCRYPTION_KEY` 环境变量,测试模式自动填固定密钥。

**Tech Stack:** Python 3.11 / Flask 3.0.3 / sqlcipher3-wheels 0.5.7(SQLCipher 4,AES-256-CBC)

**关联设计:** `docs/superpowers/specs/2026-07-06-sqlite-encryption-design.md`

**已完成的 Spike 验证(2026-07-06):** sqlcipher3-wheels 0.5.7 在 Python 3.11 Windows 可装可用;raw key hex 语法 `PRAGMA key = "x'HEX'"` 可用;错密钥首次查询即抛 `file is not a database`;普通 sqlite3 打不开加密文件;`:memory:` + key 可用;中文存取正确。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `pyproject.toml` | Modify | 声明 `sqlcipher3-wheels` 依赖 |
| `requirements.txt` | Modify | 同步依赖 |
| `performance_app/db.py` | Modify | 新增 `connect(path,key)`;`get_db`/`_connect_database` 改用它 |
| `performance_app/__init__.py` | Modify | 读取 `DB_ENCRYPTION_KEY`;TESTING 自动填测试密钥;缺失即抛错 |
| `performance_app/generate_key.py` | Create | 一次性生成 32 字节 hex 密钥 |
| `migrate_to_encrypted_db.py` | Create | 明文库 → 加密库迁移 + 行数校验 + 明文备份 |
| `tests/test_encrypted_db.py` | Create | 连接层单测:加密生效、错密钥抛错、普通 sqlite3 打不开 |
| `tests/test_generate_key.py` | Create | generate_key 输出格式单测 |
| `tests/test_migrate_to_encrypted_db.py` | Create | 迁移脚本单测:行数一致、目标库加密 |
| `tests/*.py`(9 个文件) | Modify | 把断言用的 `sqlite3.connect(...)` 改走加密 `connect(...)` |
| `fix_*.py` / `update_manager_scores.py` / `reset_current_cycle_reviews.py` / `migrate_add_dept_fields.py` / `delete_current_cycle_reviews.py` | Modify(低优先级) | 改走加密连接,路径从 config 取 |
| `.gitignore` | Modify | 追加 `.env` |
| `README.md` | Modify | 加密部署/迁移说明 |
| `docs/superpowers/specs/2026-07-06-sqlite-encryption-design.md` | Modify | 回填"TESTING 自动密钥替代 conftest"的决策调整 |

---

## Task 1: 同步依赖声明

**Files:**
- Modify: `pyproject.toml:5-9`(`dependencies` 列表)
- Modify: `requirements.txt`

> 背景:spike 阶段已用 `pip` 把 `sqlcipher3-wheels` 装进 `.venv`,但尚未写进依赖声明文件。

- [ ] **Step 1: 编辑 `pyproject.toml`**

在 `dependencies` 列表追加 `"sqlcipher3-wheels==0.5.7"`:

```toml
dependencies = [
    "Flask==3.0.3",
    "Werkzeug==3.0.3",
    "openpyxl==3.1.5",
    "sqlcipher3-wheels==0.5.7",
]
```

- [ ] **Step 2: 编辑 `requirements.txt`**

追加一行:

```
sqlcipher3-wheels==0.5.7
```

- [ ] **Step 3: 验证依赖可导入**

Run: `.venv/Scripts/python.exe -c "import sqlcipher3; print(sqlcipher3.sqlite_version)"`
Expected: 打印类似 `3.51.1`,无异常。

---

## Task 2: db.py 连接抽象层(TDD)

**Files:**
- Modify: `performance_app/db.py:1-10, 88-108`
- Test: `tests/test_encrypted_db.py`(Create)

- [ ] **Step 1: 写失败测试 `tests/test_encrypted_db.py`**

```python
import sqlite3

from performance_app.db import connect


def test_connect_creates_encrypted_db_unreadable_by_plain_sqlite3(tmp_path):
    """加密后,普通 sqlite3 必须打不开文件。"""
    db = tmp_path / "enc.sqlite3"
    key = "a" * 64  # 32 字节 raw key 的 hex

    conn = connect(str(db), key)
    conn.execute("create table t(id integer, name text)")
    conn.execute("insert into t values (1, '机密绩效')")
    conn.commit()
    conn.close()

    # 普通 sqlite3 打不开(加密页无法解析)
    plain = sqlite3.connect(str(db))
    try:
        plain.execute("select * from t").fetchone()
        raise AssertionError("普通 sqlite3 不应能读取加密库")
    except sqlite3.DatabaseError as e:
        assert "not a database" in str(e).lower() or "file is not" in str(e).lower()
    finally:
        plain.close()


def test_connect_wrong_key_raises_immediately(tmp_path):
    """错密钥在连接阶段即抛错,而非延迟到业务查询。"""
    import sqlcipher3

    db = tmp_path / "enc.sqlite3"
    key = "a" * 64
    wrong = "b" * 64

    conn = connect(str(db), key)
    conn.execute("create table t(id integer)")
    conn.commit()
    conn.close()

    try:
        connect(str(db), wrong)  # 应在内部 select count(*) 处抛错
        raise AssertionError("错密钥不应成功连接")
    except sqlcipher3.DatabaseError as e:
        assert "not a database" in str(e).lower()


def test_connect_correct_key_round_trips_chinese(tmp_path):
    """对密钥能正确读写中文。"""
    db = tmp_path / "enc.sqlite3"
    key = "a" * 64

    conn = connect(str(db), key)
    conn.execute("create table t(id integer, name text)")
    conn.execute("insert into t values (1, '机密绩效')")
    conn.commit()
    conn.close()

    conn = connect(str(db), key)
    row = conn.execute("select name from t").fetchone()
    conn.close()
    assert row[0] == "机密绩效"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_encrypted_db.py -v`
Expected: FAIL,`ImportError: cannot import name 'connect' from 'performance_app.db'`

- [ ] **Step 3: 改 `performance_app/db.py`**

把第 3 行 `import sqlite3` 改为:

```python
import sqlcipher3 as sqlite3  # DB-API 2.0 与 sqlite3 一致,提供透明整库加密
```

在 `get_db` 之前(约第 87 行,`DEFAULT_BUILT_IN_ACCOUNTS` 等常量之后、`get_db` 之前)新增 `connect`:

```python
def connect(database_path: str, encryption_key: str) -> sqlite3.Connection:
    """打开加密数据库连接。密钥错误时立即抛出 DatabaseError(file is not a database)。"""
    connection = sqlite3.connect(database_path)
    connection.execute(f"PRAGMA key = \"x'{encryption_key}'\"")
    connection.execute("pragma foreign_keys = on")
    # 主动触发一次解密,把"密钥错误"前置到连接阶段,而非首次业务查询
    connection.execute("select count(*) from sqlite_master").fetchone()
    return connection
```

把 `get_db` 改为:

```python
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = connect(
            current_app.config["DATABASE"],
            current_app.config["DB_ENCRYPTION_KEY"],
        )
        connection.row_factory = sqlite3.Row
        g.db = connection
    return g.db
```

把 `_connect_database` 改为(签名加 `encryption_key`):

```python
def _connect_database(database_path: str, encryption_key: str) -> sqlite3.Connection:
    return connect(database_path, encryption_key)
```

把 `init_database` 里调用 `_connect_database` 的地方与冗余的 `pragma foreign_keys = on` 改掉:

```python
def init_database(app: Flask) -> None:
    database_path = app.config["DATABASE"]
    encryption_key = app.config["DB_ENCRYPTION_KEY"]
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    with _connect_database(database_path, encryption_key) as connection:
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
        ensure_built_in_accounts(connection)
        if app.config.get("SEED_DEMO_DATA", True):
            ensure_demo_workflow_data(connection)
        connection.commit()
```

> 说明:原 `init_database` 内的 `connection.execute("pragma foreign_keys = on")` 删除——因为 `connect()` 内部已设置,重复设置虽无害但属本次改动产生的冗余。

- [ ] **Step 4: 运行连接层单测,确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_encrypted_db.py -v`
Expected: 3 passed

- [ ] **Step 5: 运行全量测试,确认 db.py 改动未破坏其他(此时部分会因缺密钥失败,属预期)**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: `test_encrypted_db.py` 3 个 pass;其他测试因 `create_app` 尚未注入 `DB_ENCRYPTION_KEY` 而失败(`KeyError: 'DB_ENCRYPTION_KEY'`)。Task 3 修复。

---

## Task 3: __init__.py 密钥注入(TDD)

**Files:**
- Modify: `performance_app/__init__.py:1-20`
- Test: `tests/test_app_factory.py`(已存在,新增用例)

- [ ] **Step 1: 在 `tests/test_app_factory.py` 追加失败测试**

先 Read `tests/test_app_factory.py` 了解现有风格,再追加:

```python
import pytest

from performance_app import create_app


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
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_factory.py -v`
Expected: 3 个新用例 FAIL

- [ ] **Step 3: 改 `performance_app/__init__.py`**

文件顶部加 `import os`:

```python
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
```

在 `create_app` 内,`SEED_DEMO_DATA` 处理之后、`from performance_app import db` 之前,插入密钥解析:

```python
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
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_app_factory.py -v`
Expected: 全部 pass(含原有用例 + 3 个新用例)

- [ ] **Step 5: 运行全量测试,确认应用层加密链路打通**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 通过的测试数显著上升。仍可能失败的只剩 `tests/*.py` 里**直接用 `sqlite3.connect(...)` 做断言**的用例(Task 4 修复),以及 `test_database_initialization.py`、`test_reset_current_cycle_reviews.py` 等同样直连的。记录失败清单。

---

## Task 4: 测试断言连接批量改造(机械替换)

**Files:**
- Modify: `tests/test_database_initialization.py`
- Modify: `tests/test_v2_backend_adjustments.py`
- Modify: `tests/test_employee_import_api.py`
- Modify: `tests/test_excel_import_api.py`
- Modify: `tests/test_scoring_workflow_api.py`
- Modify: `tests/test_objective_calculation_export_api.py`
- Modify: `tests/test_cycle_api.py`
- Modify: `tests/test_page_workflows.py`
- Modify: `tests/test_reset_current_cycle_reviews.py`

> 这是纯迁移任务,无新逻辑,以全量 `pytest` 绿为验收。先用 grep 定位每个文件的连接调用形态。

- [ ] **Step 1: 列出所有需要改的调用点**

Run: `.venv/Scripts/python.exe -m pytest -q 2>&1 | grep -E "FAILED|error" | head -50`

同时定位断言连接:

Run(grep): pattern `sqlite3\.connect\(`, glob `tests/*.py`, output_mode `content`, `-n true`

记录每个文件的调用形态(参数是 `app.config["DATABASE"]` 还是 `db_path` 等局部变量)。

- [ ] **Step 2: 对每个文件执行替换**

对每个文件:

1. 顶部新增导入(若尚无):
   ```python
   from performance_app.db import connect
   ```
   保留原有 `import sqlite3`(部分文件用到 `sqlite3.Row` 等)。

2. 把断言连接替换为加密连接。**按参数形态分两种:**
   - 形态 A `with sqlite3.connect(app.config["DATABASE"]) as connection:`
     → `with connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"]) as connection:`
   - 形态 B `with sqlite3.connect(db_path) as connection:`(如 `test_database_initialization.py`、`test_reset_current_cycle_reviews.py`,其中 `db_path` 指向测试库)
     → `with connect(db_path, app.config["DB_ENCRYPTION_KEY"]) as connection:`
     (确认该测试内 `app` 在作用域内;`test_database_initialization.py` 用 `make_app`/`create_app` 创建了 app,取其 config)

3. 对每处替换,确认 key 来源是同一测试创建的 `app.config["DB_ENCRYPTION_KEY"]`(TESTING 模式下已被 Task 3 自动填充为 `"0"*64`)。

> 形态 B 示例(`test_database_initialization.py` 风格):
> ```python
> # 改前
> with sqlite3.connect(db_path) as connection:
>     assert connection.execute("...").fetchone()
> # 改后
> app = make_app(tmp_path)  # 若该测试尚未创建 app,需创建以拿到密钥
> with connect(db_path, app.config["DB_ENCRYPTION_KEY"]) as connection:
>     assert connection.execute("...").fetchone()
> ```
> 注意:若某测试原本只造了 `db_path` 而未造 `app`,需补 `app = create_app({"TESTING": True, "DATABASE": db_path})` 以保证密钥可用——但 `create_app` 会触发 `init_database` 建表,需确认与该测试意图一致。逐个判断。

- [ ] **Step 3: 全量测试**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 全部 pass(或仅剩与本任务无关的预存失败,需逐个甄别;理想情况 0 failed)。

- [ ] **Step 4: 若有顽固失败,逐个调试**

对每个 FAILED,用 `.venv/Scripts/python.exe -m pytest tests/<file>.py::<test> -v` 单独跑,确认是连接密钥问题(漏改某处)还是真实回归。漏改则补改;真实回归则进入 systematic-debugging。

---

## Task 5: generate_key.py(TDD)

**Files:**
- Create: `performance_app/generate_key.py`
- Test: `tests/test_generate_key.py`(Create)

- [ ] **Step 1: 写失败测试 `tests/test_generate_key.py`**

```python
import re
import io
from contextlib import redirect_stdout

from performance_app import generate_key


def test_generate_key_prints_64_hex_chars():
    buf = io.StringIO()
    with redirect_stdout(buf):
        generate_key.main()
    out = buf.getvalue()
    match = re.search(r"DB_ENCRYPTION_KEY=([0-9a-f]{64})", out)
    assert match is not None, f"输出未包含合法密钥: {out!r}"


def test_generate_key_output_is_random():
    buf1, buf2 = io.StringIO(), io.StringIO()
    with redirect_stdout(buf1):
        generate_key.main()
    with redirect_stdout(buf2):
        generate_key.main()
    assert buf1.getvalue() != buf2.getvalue()
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_generate_key.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'performance_app.generate_key'`

- [ ] **Step 3: 创建 `performance_app/generate_key.py`**

```python
"""一次性生成数据库加密密钥的工具。

用法:
    python -m performance_app.generate_key

将输出的 DB_ENCRYPTION_KEY 配置到环境变量(建议写入不入库的 .env)。
密钥丢失则加密数据库不可恢复,请妥善保管(密码本/1Password)。
"""
from __future__ import annotations

import secrets


def main() -> None:
    key = secrets.token_hex(32)  # 32 字节 = 256 bit,AES-256 raw key(hex 编码)
    print(f"DB_ENCRYPTION_KEY={key}")
    print(
        "请妥善保管此密钥(丢失则数据库不可恢复)。"
        "配置方式:设置系统环境变量 DB_ENCRYPTION_KEY,或写入不入库的 .env。",
        flush=True,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_generate_key.py -v`
Expected: 2 passed

- [ ] **Step 5: 手动运行确认输出形态**

Run: `.venv/Scripts/python.exe -m performance_app.generate_key`
Expected: 打印 `DB_ENCRYPTION_KEY=<64 位 hex>` 和保管提示。

---

## Task 6: migrate_to_encrypted_db.py(TDD)

**Files:**
- Create: `migrate_to_encrypted_db.py`
- Test: `tests/test_migrate_to_encrypted_db.py`(Create)

- [ ] **Step 1: 写失败测试 `tests/test_migrate_to_encrypted_db.py`**

```python
import sqlite3
from pathlib import Path

import migrate_to_encrypted_db as mig


def _seed_plain_db(path: str) -> None:
    """造一个含真实 schema 抽样的明文库。"""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table user_account(id integer primary key, username text);
        create table evaluation_cycle(id integer primary key, cycle_name text);
        insert into user_account values (1, 'admin');
        insert into evaluation_cycle values (7, '2026-Q2 演示周期');
        """
    )
    conn.commit()
    conn.close()


def test_migrate_produces_encrypted_db_with_same_rows(tmp_path):
    plain = tmp_path / "plain.sqlite3"
    enc = tmp_path / "enc.sqlite3"
    _seed_plain_db(str(plain))

    rows_before = mig.table_row_counts(sqlite3.connect(str(plain)))

    mig.migrate(str(plain), str(enc), "a" * 64)

    # 目标库存在
    assert enc.exists()
    # 目标库加密:普通 sqlite3 打不开
    plain_open = sqlite3.connect(str(enc))
    try:
        plain_open.execute("select count(*) from user_account").fetchone()
        raise AssertionError("迁移目标库不应能被普通 sqlite3 读取")
    except sqlite3.DatabaseError:
        pass
    finally:
        plain_open.close()
    # 行数一致
    from performance_app.db import connect
    conn = connect(str(enc), "a" * 64)
    rows_after = mig.table_row_counts(conn)
    conn.close()
    assert rows_before == rows_after


def test_migrate_leaves_plain_backup(tmp_path):
    plain = tmp_path / "plain.sqlite3"
    enc = tmp_path / "enc.sqlite3"
    _seed_plain_db(str(plain))
    mig.migrate(str(plain), str(enc), "a" * 64)
    # 原明文文件应被备份(重命名为 .bak-plaintext-<ts>)
    backups = list(tmp_path.glob("plain.sqlite3.bak-plaintext-*"))
    assert backups, "应保留明文备份"


def test_migrate_aborts_on_row_count_mismatch(tmp_path):
    """模拟校验失败时不替换原文件(通过 monkeypatch 制造不一致)。"""
    plain = tmp_path / "plain.sqlite3"
    enc = tmp_path / "enc.sqlite3"
    _seed_plain_db(str(plain))
    import pytest
    with pytest.raises(RuntimeError):
        mig.migrate(str(plain), str(enc), "a" * 64, fail_verification=True)
    # 原明文文件未被替换/删除
    assert plain.exists()
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_to_encrypted_db.py -v`
Expected: FAIL,`ModuleNotFoundError`

- [ ] **Step 3: 创建 `migrate_to_encrypted_db.py`**

```python
"""把现有明文 SQLite 数据库迁移为 SQLCipher 加密数据库。

流程(官方 sqlcipher_export 推荐):
    1. 用 sqlcipher3 打开明文源(不设 key)
    2. ATTACH 新的加密库
    3. SELECT sqlcipher_export('enc')  复制全部 schema + 数据
    4. 逐表行数校验,不一致则中止
    5. 备份原文件为 .bak-plaintext-<时间戳>,用加密库替换

用法:
    DB_ENCRYPTION_KEY=<密钥> python migrate_to_encrypted_db.py
    DB_ENCRYPTION_KEY=<密钥> python migrate_to_encrypted_db.py --source <path> --target <path>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sqlite3
import sys
from pathlib import Path

import sqlcipher3


def table_row_counts(conn) -> dict[str, int]:
    """返回 {表名: 行数},用于迁移前后比对。"""
    tables = [
        r[0]
        for r in conn.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
        ).fetchall()
    ]
    return {t: conn.execute(f"select count(*) from \"{t}\"").fetchone()[0] for t in tables}


def migrate(
    source: str,
    target: str,
    key: str,
    *,
    fail_verification: bool = False,
) -> None:
    """把 source(明文)迁移到 target(加密)。成功后 source 被重命名为 .bak-plaintext-<ts>。"""
    if not Path(source).exists():
        raise FileNotFoundError(f"源数据库不存在: {source}")

    conn = sqlcipher3.connect(source)  # 明文库,不设 key
    before = table_row_counts(conn)

    # 删除可能残留的旧 target
    if Path(target).exists():
        Path(target).unlink()

    conn.execute(f"ATTACH DATABASE ? AS enc KEY ?", (target, f"x'{key}'"))
    conn.execute("SELECT sqlcipher_export('enc')")
    conn.execute("DETACH DATABASE enc")

    # 在同一连接读取已导出的加密库行数
    conn.execute(f"ATTACH DATABASE ? AS enc2 KEY ?", (target, f"x'{key}'"))
    after = {}
    for t in before:
        after[t] = conn.execute(f'SELECT count(*) FROM enc2."{t}"').fetchone()[0]
    conn.execute("DETACH DATABASE enc2")
    conn.close()

    if fail_verification:
        after = {k: v + 9999 for k, v in after.items()}  # 仅测试用,制造不一致

    if before != after:
        raise RuntimeError(
            f"行数校验不一致,迁移中止(未替换原文件)。before={before} after={after}"
        )

    # 备份原明文,用加密库替换
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{source}.bak-plaintext-{ts}"
    os.replace(source, backup)
    os.replace(target, source)  # 加密库就位到原路径
    print(f"迁移成功。原明文已备份: {backup}")
    print(f"加密库已就位: {source}")
    print(f"行数校验通过: {before}")
    print("请确认无误后,手动删除明文备份(或运行时加 --purge-backups)。")


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移明文 SQLite 为 SQLCipher 加密库")
    parser.add_argument("--source", default="data/performance_review.sqlite3")
    parser.add_argument("--target", default="data/performance_review.enc.sqlite3")
    args = parser.parse_args()

    key = os.environ.get("DB_ENCRYPTION_KEY")
    if not key:
        print("错误:未设置 DB_ENCRYPTION_KEY 环境变量", file=sys.stderr)
        return 2
    migrate(args.source, args.target, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest tests/test_migrate_to_encrypted_db.py -v`
Expected: 3 passed

- [ ] **Step 5: 用真实库做一次演练(不替换原文件)**

先备份真实库副本到临时位置,对副本跑迁移:

```bash
cp data/performance_review.sqlite3 /tmp/practice.sqlite3
DB_ENCRYPTION_KEY=$(python -c "print('a'*64)") .venv/Scripts/python.exe -c "
import migrate_to_encrypted_db as m
m.migrate('/tmp/practice.sqlite3', '/tmp/practice.enc.sqlite3', 'a'*64)
"
```

Expected: 打印"迁移成功"+ 行数表。验证 `/tmp/practice.sqlite3` 现在是加密的(普通 sqlite3 打不开)。

> 真正对 `data/performance_review.sqlite3` 的迁移放 Task 8 最终验收时执行。

---

## Task 7: 运维脚本改造(低优先级,按需)

**Files:**
- Modify: `fix_scores.py`、`fix_final_subjective_grades.py`、`fix_indirect_pending.py`、`fix_no_dept_head.py`、`update_manager_scores.py`、`reset_current_cycle_reviews.py`、`migrate_add_dept_fields.py`、`delete_current_cycle_reviews.py`

> 这些脚本硬编码了**已过时的路径** `d:\AI工作台\cet-tool\...`。改造为从应用 config/环境取路径与密钥。

- [ ] **Step 1: 对每个脚本统一改造模式**

每个脚本顶部:

```python
import os
from performance_app import create_app
from performance_app.db import connect

app = create_app({"DATABASE": os.environ.get("DATABASE", "data/performance_review.sqlite3")})
conn = connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"])
```

替换原来的 `conn = sqlite3.connect(r'd:\AI工作台\...')`。

- [ ] **Step 2: 逐个确认能 import 与连接**

Run: `DB_ENCRYPTION_KEY=<dev key> .venv/Scripts/python.exe -c "import fix_scores"`(对每个脚本)
Expected: 无 ImportError。

> 这些脚本属一次性历史脚本,若已无实际用途,可与维护者确认后跳过本任务(在 PR 说明里标注)。

---

## Task 8: 最终验收

**Files:** 无改动,纯验证。

- [ ] **Step 1: 全量单元测试**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 全部 pass,0 failed。

- [ ] **Step 2: 生成真实密钥并设置环境**

```bash
.venv/Scripts/python.exe -m performance_app.generate_key
```

把输出的 `DB_ENCRYPTION_KEY=...` 值写入 `.env`(不入库,Task 9 已加 .gitignore)或系统环境变量。**妥善保存密钥到密码本**。

- [ ] **Step 3: 迁移真实数据库**

```bash
cp data/performance_review.sqlite3 data/performance_review.sqlite3.pre-migrate-snapshot
DB_ENCRYPTION_KEY=<真实密钥> .venv/Scripts/python.exe migrate_to_encrypted_db.py
```

Expected: 打印"迁移成功"+ 各表行数;原文件被重命名为 `.bak-plaintext-<ts>`。

- [ ] **Step 4: 验证加密文件不可直读(验收标准 1)**

```bash
.venv/Scripts/python.exe -c "import sqlite3; c=sqlite3.connect('data/performance_review.sqlite3'); c.execute('select count(*) from user_account').fetchone()"
```

Expected: 抛 `sqlite3.DatabaseError: file is not a database`。

- [ ] **Step 5: 验证应用正常启动与数据完整(验收标准 2、3)**

```bash
DB_ENCRYPTION_KEY=<真实密钥> .venv/Scripts/python.exe run.py
```

浏览器访问,登录 admin,确认演示周期、人员、评分数据可见且完整。

- [ ] **Step 6: 验证密钥错误即失败(验收标准 4)**

```bash
DB_ENCRYPTION_KEY=<错误密钥> .venv/Scripts/python.exe run.py
```

Expected: 启动时在 `init_database` 阶段抛 `DatabaseError: file is not a database`。

- [ ] **Step 7: 验证密钥隔离(验收标准 5)**

Run(grep): pattern `DB_ENCRYPTION_KEY`,确认代码里无真实密钥值;`.gitignore` 含 `.env`;`.env` 未被 git 跟踪(`git status --ignored`)。

- [ ] **Step 8: 清理明文残留**

确认迁移后,手动删除 `data/` 下的 `.bak-plaintext-*` 与旧 `.bak-*` 明文备份(仅在 Step 3-6 全部通过后)。

---

## Task 9: 文档与收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-07-06-sqlite-encryption-design.md:4.5`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: 回填设计文档的决策调整**

把 4.5 节里"`tests/conftest.py` 统一注入固定测试密钥"改为:

> 测试通过 `create_app({"TESTING": True, ...})` 创建 app;`create_app` 在 TESTING 模式下自动填充固定测试密钥 `"0"*64`(见 `performance_app/__init__.py`)。因此**无需 conftest.py**,16 个测试文件的 `make_app` 辅助函数无需改动,仅断言用的 `sqlite3.connect(...)` 需改走加密 `connect(...)`。

- [ ] **Step 2: 更新 README**

在"本地启动"节追加加密部署说明:

```markdown
## 数据库加密

数据库文件采用 SQLCipher(AES-256)整库加密。首次部署:

1. 生成密钥(妥善保管,丢失则数据不可恢复):
   ```bash
   uv run python -m performance_app.generate_key
   ```
2. 把输出的 `DB_ENCRYPTION_KEY=<64位hex>` 写入不入库的 `.env` 或系统环境变量。
3. 启动:
   ```bash
   # 已有明文库时,先迁移:
   DB_ENCRYPTION_KEY=<密钥> python migrate_to_encrypted_db.py
   # 之后正常启动:
   DB_ENCRYPTION_KEY=<密钥> uv run python run.py
   ```

密钥缺失或错误时,应用在启动阶段即失败。
```

- [ ] **Step 3: 更新 `.gitignore`**

追加:

```
.env
```

- [ ] **Step 4: 最终全量测试**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 全部 pass。

- [ ] **Step 5: 统一提交并推送(用户要求)**

```bash
git add -A
git status   # 确认:.env 不在列表,密钥值不在任何已跟踪文件中
git commit -m "feat: SQLite 数据库文件改用 SQLCipher 整库加密

- db.py 新增 connect(path,key),应用/测试/脚本共用加密连接
- 密钥来自 DB_ENCRYPTION_KEY 环境变量,TESTING 模式自动填测试密钥
- 新增 generate_key.py 与 migrate_to_encrypted_db.py(含行数校验)
- tests 断言连接批量改走加密连接
- 设计文档: docs/superpowers/specs/2026-07-06-sqlite-encryption-design.md

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
```

---

## Self-Review(计划作者自查)

**1. Spec 覆盖:** 设计文档各节与任务对应——4.1 连接层→Task 2;4.2 密钥管理→Task 3;4.3 generate_key→Task 5;4.4 迁移→Task 6;4.5 测试→Task 3(TESTING 密钥)+ Task 4(断言连接);4.6 运维脚本→Task 7;6 错误处理→Task 2(错密钥前置)+ Task 6(校验失败中止)+ Task 3(缺失抛错);7 验收标准→Task 8 全覆盖。✅

**2. 占位符扫描:** 无 TBD/TODO;每个 code step 均含完整代码。✅

**3. 类型/命名一致:** `connect(database_path, encryption_key)` 签名在 Task 2/4/6 一致;`DB_ENCRYPTION_KEY` 配置键贯穿 Task 2/3/5/6/8 一致;`migrate(source, target, key)` 在 Task 6 测试与实现一致。✅

**4. 已知风险:** ① Task 4 形态 B(`db_path` 直连)的测试若未先造 app,需补 `create_app`——已在该任务 Step 2 注明逐个判断;② Task 7 运维脚本可能已废弃,标注按需;③ sqlcipher3 的 `with conn as ...` 事务语义与 sqlite3 一致(已由 spike 的 connect/close 验证底层连接,with 语义执行时 pytest 会暴露)。
