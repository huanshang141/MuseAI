# 后端变更日志

## 2026-07-15

- 建立数据驱动后端框架任务。
- 确认 Excel/CSV 输入、纯游客 session、A/B/C/D 问卷人格、动态报告和 2C8G 资源基线。
- 新增纯游客 session token、完整恢复状态、每展厅最近 20 条会话和最多 9 个展厅的恢复上限，并以状态版本防止并发覆盖。
- 快速开始使用独立 `default` 人格；问卷使用 A/B/C/D；删除公开注册入口，普通账号不能登录，管理员由引导脚本初始化。
- 新增 Excel/CSV 馆方数据校验、幂等导入、来源追踪、RAG 激活回滚与数据驱动建议问题。
- 对话只从数据库读取可信展厅/展品事实；报告重复打开时按当前时间刷新总时长。
- 数据库迁移 head：`20260715_data_driven_tour`。
- 验证：最终 focused 后端测试 205 passed；本次变更 Python 文件 Ruff 通过；Alembic 单一 head。
- PATCH 会在写入前校验当前展品真实存在、处于启用状态且属于有效展厅；仅切换展厅时也校验保留展品，避免无效外键或跨厅状态。
- 数据导入在写入前拒绝同来源、同展厅 slug 改换非空 `source_record_id`；相关 API/导入 focused 测试 52 passed，scoped Ruff 通过。
- 创建游客会话与生成报告的 POST 路由已接入独立限流依赖；报告生成同时传入数据库展厅名称映射；限流依赖测试 46 passed。
- 报告首次并发生成时复用唯一报告记录；Nginx 在读取游客状态前执行 2 MiB 限制；动态总时长保证不出现负数。
- 补充超过 24 小时后的同值开始时间恢复、人格不可变、任意风格文本拒绝及导入展厅真实名称进入报告摘要的回归测试。
- 修复同批次停用展厅与展品时的组合回滚：某展品旧 RAG 删除失败时恢复该展品及所属展厅原 active 状态，其他成功删除的展厅/展品仍正常停用；importer 测试 20 passed。
- 公开展品 catalog、筛选与普通名称搜索统一采用馆方 `display_order` 升序、空值后置，再以创建时间和 ID 稳定兜底；Hall 表有记录但全部停用时返回空列表，不再复活静态展厅；相关真实 repository/API/Tour 测试 65 passed。
- 新增显式 `--authoritative` 完整快照接管：默认导入仍非破坏；权威模式只停用同来源遗漏项和无来源旧占位项，其他来源不变。停用旧展品前同时清理 exhibit source 与旧 `document_id/document` 向量，任一删除失败恢复对应展品和展厅并非零退出，不删除 Document/IngestionJob 数据库记录。
- 移除公开展品名称黑名单；同名真实馆方记录正常显示，列表 `total` 与数据库分页结果一致。
- `/tour/halls` 以单批展品查询返回真实 `highlights`（最多 3 条）和由 Hall.description 截取的 `focus`；空展厅不填入假展品。
- 报告展品浏览数只统计真实 `exhibit_id`；移除固定展厅权重、旧占位事实模板和文化特定身份标签。一句话、标签、复盘及记录摘要改为确定性统计、实际问答和数据库展厅名，不再为报告调用 LLM。
- 对话检索会按 `Exhibit.document_id` 校验旧 document 分片，仅允许当前展厅启用展品关联的分片，同时保留未关联展品的通用馆方文档。
- 最终验证：关键组合 159 passed；全后端 1073 passed、23 skipped（17 条既有 warning）；本次变更 scoped Ruff 与 `git diff --check` 通过。
- 提交 SHA：见本提交。推送分支：`codex/data-driven-miniapp-framework`。

## 2026-07-16

- 生产部署验证发现长期运行的 `uv run uvicorn` 会使新的 `uv run` 运维命令等待；systemd unit 改为直接调用 checkout 内 `.venv/bin/alembic` 和 `.venv/bin/uvicorn`。
- 部署说明补充每次切换提交后先执行 `uv sync --frozen`，确保 systemd 使用的虚拟环境与目标提交一致。
- PostgreSQL、Redis 与 Elasticsearch 的 Compose 端口只绑定 `127.0.0.1`，避免无认证基础服务暴露到公网。
