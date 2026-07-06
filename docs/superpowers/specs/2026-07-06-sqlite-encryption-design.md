# SQLite 数据库文件加密设计

- 日期:2026-07-06
- 状态:待评审
- 作者:zhangpulong + Claude
- 关联代码:`performance_app/db.py`、`performance_app/__init__.py`、`tests/`、根目录运维脚本

## 1. 背景与目标

当前应用 `data/performance_review.sqlite3` 是**明文** SQLite 文件,任何拿到该文件的人(DB Browser、`sqlite3` 命令、文本编辑器)都能直接读到绩效明细、员工信息、账号密码哈希。

**目标**:对数据库文件做整库加密,使文件脱离应用后无法被直接读取,并满足合规审计"数据库文件加密存储 + 密钥管理可说明"的要求。

**非目标**(本期不做):
- 防止有服务器登录权的运维绕过程序直接改库(运行时密钥必在内存,文件加密无法解决此威胁)。
- 防止整台服务器被物理拿走(密钥仍在本机,如需可后续引入外部 KMS)。
- 网络传输加密(由反向代理/HTTPS 承担,与本文档无关)。

## 2. 威胁模型

| 威胁 | 是否覆盖 | 说明 |
|---|---|---|
| DB 文件被拷贝/备份/误传后直接打开 | ✅ 覆盖 | 文件无密钥即乱码 |
| 合规审计要求出示加密证据 | ✅ 覆盖 | AES-256-CBC + 密钥环境变量隔离 |
| 运维登录服务器后直接 `sqlite3` 改分 | ❌ 不覆盖 | 运维可读到环境变量里的密钥 |
| 服务器整机失窃 | ❌ 不覆盖 | 密钥与数据同机 |

## 3. 方案选型

**采用 SQLCipher 透明整库加密**(实现包:`sqlcipher3-wheels`)。

对比过的备选:
- 应用层字段加密:破坏 `WHERE`/`ORDER BY`/排名筛选,改动侵入每个 repository,口径碎。否决。
- 文件系统加密(BitLocker/LUKS):零代码,但合规口径是"磁盘加密"非"数据库加密",甲方大概率不认。否决。

选 SQLCipher 的理由:整库 AES-256;SQL 语法不变,应用代码无感知;有 Win/Linux 预编译 wheel(`sqlcipher3-wheels` 内置 SQLCipher 4 amalgamation,无外部 C 依赖);合规标准答案。

## 4. 架构设计

### 4.1 连接抽象层(核心,位于 `performance_app/db.py`)

当前所有连接集中在 `db.py` 的 `get_db()` 与 `_connect_database()`。改造为一个公共连接工厂,应用、测试、运维脚本共用,避免散落:

```python
# db.py 关键形态(示意,最终以 plan 实现为准)
import sqlcipher3 as sqlite3  # sqlcipher3 的 DB-API 2.0 与 sqlite3 完全一致

def connect(database_path: str, encryption_key: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    # raw key(hex,32 字节)直接作为 AES-256 密钥,无 KDF,合规口径明确
    connection.execute(f"PRAGMA key = \"x'{encryption_key}'\"")
    connection.execute("pragma foreign_keys = on")
    # 主动触发一次解密,把"密钥错误"前置到连接时而非首次业务查询
    connection.execute("select count(*) from sqlite_master").fetchone()
    return connection

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"],
                       current_app.config["DB_ENCRYPTION_KEY"])
        g.db.row_factory = sqlite3.Row
    return g.db
```

`import sqlcipher3 as sqlite3` 后,现有代码里的 `sqlite3.Row`、`sqlite3.Connection` 类型注解全部继续生效,无需改动。

### 4.2 密钥管理

- **格式**:32 字节(256 bit)密码学随机数,以 64 位 hex 字符串表示,作为 SQLCipher raw key(无 KDF 派生,确定性、合规可述)。
- **来源**:环境变量 `DB_ENCRYPTION_KEY`。生产部署时由运维写入系统环境变量或不入库的 `.env`,仅 Flask 服务账号可读。
- **注入**:`performance_app/__init__.py` 的 `create_app` 读取 `DB_ENCRYPTION_KEY` 写入 `app.config`。
- **缺失处理**:生产环境变量缺失 → `create_app` 抛 `RuntimeError` 并明确提示"未设置 DB_ENCRYPTION_KEY";测试环境由 conftest 注入固定测试密钥,不依赖环境。
- **不入库**:`.gitignore` 追加 `.env`;密钥绝不写入代码或配置文件提交。

### 4.3 密钥生成脚本(新增 `performance_app/generate_key.py`)

一次性辅助脚本,生成合规强度的随机密钥并打印,供运维首次部署使用:

```bash
uv run python -m performance_app.generate_key
# 输出:DB_ENCRYPTION_KEY=2dd29ca851e7b56e4697b0e1f08507293d761a05ce4d1b628663f411a8086d99
```

实现用 `secrets.token_hex(32)`。

### 4.4 现有数据迁移(新增 `migrate_to_encrypted_db.py`)

`data/performance_review.sqlite3` 含真实数据(116K),必须迁移。采用 SQLCipher 官方推荐的 `sqlcipher_export()` 流程,保证 schema + 数据 + 外键完整:

```
1. 用 sqlcipher3 打开旧明文库(不设 key)
2. ATTACH DATABASE '<临时加密库>' AS enc KEY '<raw key>'
3. SELECT sqlcipher_export('enc')        -- 复制全部 schema 与数据
4. DETACH DATABASE enc
5. 行数校验:逐表比对源库与加密库行数一致
6. 备份原文件为 .bak-plaintext-<时间戳>,用加密库替换
7. 打印迁移报告(各表行数、原/新文件大小)
```

校验失败则不替换原文件,保留明文备份,脚本以非零码退出。

### 4.5 测试改造(`tests/`,工作量最大)

现状:`tests/*.py` 有 40+ 处 `sqlite3.connect(app.config["DATABASE"])` 直接打开库做断言。加密后这些连接打不开文件。

改造方式(机械替换,批量进行):
- 每个测试文件 `import sqlite3` → 调用 `performance_app.db.connect(app.config["DATABASE"], app.config["DB_ENCRYPTION_KEY"])`。
- 密钥由 `create_app` 在 TESTING 模式自动填充固定测试密钥 `"0"*64`(见 `performance_app/__init__.py`),**无需 conftest.py**;`make_app(tmp_path)` 辅助函数无需改动,仅断言用的 `sqlite3.connect(...)` 改走 `performance_app.db.connect(...)`。
- `:memory:` 模式:sqlcipher3 支持,同样需 `PRAGMA key`;`init_database` 对 `:memory:` 已有分支,沿用。

### 4.6 运维脚本(最低优先级,按需)

根目录 `fix_*.py`、`migrate_add_dept_fields.py`、`reset_current_cycle_reviews.py`、`update_manager_scores.py`、`delete_current_cycle_reviews.py` 现状是直接 `sqlite3.connect` 且硬编码了**已过时的路径**(`d:\AI工作台\cet-tool\...`)。

处理策略:改为调用 `performance_app.db.connect(路径, 密钥)`,路径与密钥从 `create_app` 的 config / 环境变量取,不再硬编码。因属一次性历史脚本,排在测试改造之后,可逐个按需进行。

## 5. 数据流

- **启动**:`create_app` 读 `DB_ENCRYPTION_KEY` → `init_database` 经 `connect()` 打开/创建加密库 → 建表、种子数据 → 注册 teardown。
- **请求**:`get_db()` 经 `connect()` 取已解密连接 → 业务 SQL(sqlcipher 透明加解密页)→ 返回 Row。
- **迁移(一次性)**:明文库 → `sqlcipher_export` → 加密库 → 校验 → 替换。

## 6. 错误处理

| 场景 | 行为 |
|---|---|
| 生产环境 `DB_ENCRYPTION_KEY` 缺失 | `create_app` 抛错,启动失败,提示明确 |
| 密钥错误(库已加密但 key 不匹配) | `connect()` 内 `select count(*) from sqlite_master` 抛 `DatabaseError: file is not a database`,连接阶段即暴露 |
| 迁移行数校验不一致 | 不替换原文件,保留明文备份,退出码非 0 |
| 备份 `.bak` 文件(明文)残留 | 迁移成功后提示运维手动确认并删除明文备份,或脚本提供 `--purge-backups` 可选项(默认不自动删,防误删) |

## 7. 验收标准

1. **文件不可直读**:加密后的 `performance_review.sqlite3` 用 DB Browser / `sqlite3` 命令打开,报 `file is not a database` 或显示乱码页,看不到任何表与明文。
2. **应用功能不回归**:`uv run python -m pytest -q` 全量通过(测试已改造为加密连接)。
3. **数据零丢失**:迁移后各业务表(`user_account`、`evaluation_cycle`、`cycle_employee_snapshot`、`evaluation_record`、`objective_data` 等)行数与迁移前一致;抽查关键记录(如演示周期、账号)内容一致。
4. **密钥错误即失败**:删除或篡改环境变量后启动,在连接阶段(非业务查询阶段)即报错。
5. **密钥隔离**:全仓库 `git grep DB_ENCRYPTION_KEY` 不出现真实密钥值;`.env` 在 `.gitignore` 内。

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `sqlcipher3-wheels` 在目标服务器(Python 版本/OS)装不上 | 实施第一步先做安装 spike:`uv add sqlcipher3-wheels` 后 `import sqlcipher3` 成功,再展开其余改造 |
| 测试改造量大、易漏 | 批量替换后跑全量测试兜底;`conftest` 统一注入密钥减少遗漏面 |
| 迁移中断导致数据丢失 | 脚本全程不删原文件,成功后才替换并保留 `.bak-plaintext` 备份;校验失败回滚 |
| 密钥丢失 = 数据不可恢复 | 文档明确告知运维:密钥需入密码本/1Password;丢失则库不可恢复(这是加密的固有代价) |
| 现有 `.bak` 明文备份残留 | 迁移脚本输出明文文件清单,提示运维清理 |
