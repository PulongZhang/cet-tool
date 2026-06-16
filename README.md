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

评分流、自评页面、审阅、客观数据导入、计算结果持久化、Excel 导出和页面实现按后续计划继续推进。
