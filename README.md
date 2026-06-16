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
- 账号创建、密码哈希、登录 API 和当前用户查询 API。
- JSON 行格式的人员导入服务，后续 Excel 解析会复用同一服务。
- 人员导入时自动创建周期人员快照和 `SELF_PENDING` 考核记录。
- 人员导入时自动创建员工账号，并根据直接上级、间接上级、部门负责人关系赋予角色。
- 员工自评草稿、提交和我的考核记录 API。
- 直接上级下属列表、评分草稿和提交 API，包含 A+/A/C/D 评语必填规则。
- 间接上级、部门负责人审阅列表、比例分布、提交流转 API。
- 等级调整留痕和撤回 API。
- 客观数据 JSON 行导入 API，支持 3 个月勤奋点数、纪律异常次数、学习时长转换入库，允许有效行入库并记录错误行。
- HR 计算 API，按 `final_subjective_grade_1/2/3`、客观等级和分组权重计算加权分，支持同分同排名，计算后进入 `INITIAL_CALCULATED`。
- 结果总览、个人计算明细和 HR 最终等级微调 API；最终微调只改 `final_level`，不重新计算加权分。
- 初评/最终结果 Excel 导出和下载 API，V1 当前导出 `结果总览` Sheet。

`docs/superpowers/specs/V2.md` 记录已确认澄清点；后续实现和验收以该文件中的已确认口径为准。

页面实现、客观等级人工修正、结果版本追溯、人员导入整批校验、批量提交就绪校验等 V2 澄清项按后续计划继续推进。
