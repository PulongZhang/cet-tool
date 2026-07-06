# 季度绩效考核评分工具

这是按 `docs/superpowers/specs/2026-06-16-performance-review-tool-design.md` 实现的 Flask + SQLite V1 工具。

## 本地启动

```bash
uv sync --all-groups
uv run python run.py
```

也可以继续使用 Flask CLI：

```bash
uv run python -m flask --app performance_app run --debug
```

启动时应用会读取 `DATABASE` 配置。默认数据库路径为 `data/performance_review.sqlite3`。如果数据库文件不存在，应用会自动创建父目录、SQLite 文件、业务表、索引、角色初始数据、内置角色账号、演示周期数据和 `schema_version` 记录；如果文件已存在，启动过程不会清空已有业务数据。

内置账号默认密码均为 `admin123`：

| 用户名 | 角色 |
|---|---|
| `employee` | EMPLOYEE |
| `direct` | DIRECT_MANAGER |
| `indirect` | INDIRECT_MANAGER |
| `dept` | DEPT_HEAD |
| `hr` | HRBP |
| `admin` | ADMIN + HRBP |

默认启动会在空库中创建 `2026-Q2 演示周期`，并内置一条可串完整流程的上下级关系：`employee` 的直接上级是 `direct`，间接上级是 `indirect`，部门负责人是 `dept`；`hr` 和 `admin` 可进入 HR/管理页面导入客观数据、计算和确认结果。若库中已存在周期，则不会额外追加演示周期。

## 数据库加密

数据库文件采用 SQLCipher(AES-256)整库加密,文件脱离应用后无法直接读取。首次部署:

1. 生成密钥(**妥善保管,丢失则数据不可恢复**):
   ```bash
   uv run python -m performance_app.generate_key
   ```
2. 把输出的 `DB_ENCRYPTION_KEY=<64位hex>` 写入不入库的 `.env` 或系统环境变量。
3. 若已有明文库,先迁移(脚本会自动备份明文为 `*.bak-plaintext-<时间戳>` 并做行数校验):
   ```bash
   DB_ENCRYPTION_KEY=<密钥> uv run python migrate_to_encrypted_db.py
   ```
4. 启动:
   ```bash
   DB_ENCRYPTION_KEY=<密钥> uv run python run.py
   ```

密钥缺失或错误时,应用在启动连接阶段即失败(`file is not a database` 或 `未设置 DB_ENCRYPTION_KEY`)。

## 运维脚本

如需把当前进行中周期恢复到员工可重新填写自评的初始状态，可执行：

```bash
uv run python reset_current_cycle_reviews.py
```

该脚本会先备份 `data/performance_review.sqlite3`，再删除当前 `ACTIVE` 周期下的旧 `evaluation_record` 和关联的 `grade_adjustment_log`，最后按当前周期人员快照重新生成 `SELF_PENDING` 初始评审记录；不会删除周期、人员快照、账号或客观数据。兼容入口 `delete_current_cycle_reviews.py` 也会执行同样的重置逻辑。

## 测试

```bash
uv run python -m pytest -q
```

## 当前实现范围

- Flask 应用工厂。
- SQLite 自动初始化和幂等建表。
- 角色、周期、人员快照、考核记录、调整、客观数据、导入错误和审计日志基础表。
- 评分等级、计算分组、客观数据转换、加权计算、排名定级、状态流转和数据范围判断。
- 周期创建、列表、启动、关闭、删除未启动周期 API。
- 账号创建、密码哈希、登录、退出登录 API 和当前用户查询 API。
- JSON 行格式的人员导入服务和 Excel 模板/上传解析；人员导入按 V2 口径整批校验，有错误时不写入任何人员业务数据。
- 人员导入时自动创建周期人员快照和 `SELF_PENDING` 考核记录。
- 人员导入时自动创建员工账号，并根据直接上级、间接上级、部门负责人关系赋予角色。
- 周期人员列表和导入错误查询 API。
- 员工自评草稿、提交和我的考核记录 API。
- 直接上级下属列表、评分草稿、逐人提交兼容 API 和按范围批量提交 API，包含 A+/A/C/D 评语必填规则；批量提交会校验全部下属已就绪。
- 间接上级、部门负责人审阅列表、比例分布、提交流转 API；提交前会校验范围内相关记录已全部就绪。
- 等级调整留痕和撤回 API。
- 客观数据 JSON 行导入 API 和 Excel 模板/上传解析，支持 3 个月勤奋点数、纪律异常次数、学习时长转换入库，允许有效行入库并记录错误行。
- 客观等级人工修正 API；客观数据重新导入或修正后会作废受影响人员的旧计算结果并退回 `HR_PENDING`。
- HR 计算 API，按 `final_subjective_grade_1/2/3`、客观等级和分组权重计算加权分，支持同分同排名，计算后进入 `INITIAL_CALCULATED`。
- 结果总览、个人计算明细、最终确认和 HR 最终等级微调 API；最终微调只改 `final_level`，不重新计算加权分。
- 初评/最终结果 Excel 导出和下载 API，V1 当前导出 `结果总览` Sheet。
- 功能型 Flask 前端页面：浏览器登录/退出、session 登录态、按角色显示菜单、后端页面权限拦截、首页仪表盘、周期管理、自评、直接上级评分、间接审阅、部门确认、客观数据导入、结果计算/最终确认/导出。
- 页面参考 `docs/prototypes/performance-review-tool-prototype.html` 的左侧导航、顶部用户卡、流程卡片、比例分布和表格布局；页面数据来自 SQLite 和已有服务，不再只是静态原型。

`docs/superpowers/specs/V2.md` 记录已确认澄清点；后续实现和验收以该文件中的已确认口径为准。

结果版本表/旧版本作废标记、备份运维脚本、外部消息提醒等生产运维增强项未纳入当前 V1 代码实现。
