# 后端变更日志

## 2026-08-08

- 将生产库 46 条无来源旧演示展品整理为 `data/museum_test_data` CSV 快照：名称、介绍、分类和稳定记录 ID 均明确标记为测试数据，并均匀分配到九个可信展厅；使用稳定来源 `banpo-museum-data`，后续真实权威快照可自动替换。
- 测试数据 CSV 与空展品正式模板均通过 dry-run；导入专项 33 项、展厅迁移专项 4 项通过，最终全后端回归 `1156 passed, 23 skipped, 10 warnings`，`uv lock --check`、`uv pip check` 和 `git diff --check` 通过。
- 生产部署升级到迁移 `20260808_remove_legacy_halls`；权威导入更新九厅、创建并索引 46 条测试展品、停用 46 条旧记录，`pending_index=[]`。数据库、ES、公开 API、30 条同厅恢复、OCC 冲突、SSE、报告归纳和双次有效 WAV 均通过实测。
- 生产管理员收敛为仅 `test@test.com`；原 `admin@museai.local` 降为普通用户而未删除。部署前备份为 `museai_pre_test_import_20260808_164810.sql.gz`，SHA-256 `689896c85cd13d007c03049dc71c3d377a93f31754773f8a976183a1976517fe`。
- 将九个已确认展厅 slug 固定为小程序可信白名单，名称与简介只从 Hall 数据读取；新增前向迁移和 CSV 基线一致性测试，楼层与参观时长以 `NULL`/`0` 表示尚未接入真实路线数据。
- 公开展品、游客会话、事件、建议条、聊天展品上下文和 RAG 关联文档统一要求“展品启用、展厅存在且启用、属于九厅白名单”；旧厅、停用厅、孤立展品和缺失 Hall 的关联文档均 fail-closed。
- 每厅恢复最近 30 条对话；推理保留最近 10 条原消息，将此前最多 20 条确定性压缩为一条普通历史消息，不跨厅、不新增摘要 LLM 调用。
- 临展厅一、二使用同一动态模板，仅拼接各自当前启用展品；上传、停用或删除后自动反映，不跨厅取数。
- 删除旧演示展品和破坏性初始化/导入脚本；正式数据统一使用 `data/museum_template` 的 CSV/XLSX 格式和幂等导入管线。
- 修复 SSE/TTS 资源回收、WAV/PCM 缓存边界及报告摘要归纳与并发更新；小程序传入文本不再提升为 system prompt。
- 定向最终回归：`152 passed`；新增 RAG owner、孤立展品 chat、九厅迁移/CSV 同步回归均通过。最终全量回归：`1155 passed, 23 skipped, 10 warnings`，无失败；scoped Ruff、`uv lock --check`、`uv pip check`、Alembic 单一 head 与模板 dry-run 均通过。提交、推送与部署结果在完成后补记。

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
- 修复生产依赖不可复现：停止忽略并提交 `uv.lock`，部署时先执行 `uv lock --check`、`uv sync --frozen` 和 `uv pip check`，避免服务器旧锁遗漏 `openpyxl` 等运行时依赖。
- 会话恢复允许保留已经下线展厅的历史聊天（每厅仍限制最近 20 条、总计最多 9 厅），但当前展厅和当前展品继续按启用数据严格校验。
- 会话 PATCH 对同值快照和不可写字段不再推进 `state_version` 或刷新活动时间，避免重复异步同步制造无意义的 OCC 冲突。
- 导览 SSE 在 `done` 前分别尝试持久化问答事件和展厅历史，返回最后成功写入的 `state_version`；助手事件使用与小程序一致的稳定 ID，支持前后端跨侧去重，单项持久化失败仍保持流式响应可完成。
- Excel/CSV 导入把非 UTF-8、畸形 CSV、损坏 XLSX 和缺失工作簿结构统一转换为结构化校验失败；单次文件及导入后的数据库最多保留 2000 个启用展品。
- 公开展品列表和详情新增数据库驱动的 `hall_name`；列表使用单次批量查询，未知展厅名退回规范化展示名。
- 数据导入 CLI 已分别验证 CSV、权威 CSV、XLSX 正常 dry-run，以及非法来源名、非 UTF-8 CSV、畸形 CSV、损坏 XLSX 的非零结构化失败。
- 最终验证：完整后端串行测试 `1088 passed, 23 skipped, 17 warnings`；23 项均因本机未启动 PostgreSQL、Elasticsearch、Ollama 或 Redis 而跳过，小程序核心测试无跳过。Python 3.11 与 3.12 变更组合各 `174 passed`；`uv lock --check`、两版本 `pip check`/`compileall`、scoped Ruff、mypy、Alembic 单一 head 和 `git diff --check` 均通过。
- 报告记录摘要改为受约束的单次报告模型归纳：system 仅保存规则，后端持久化问答与数据库展厅名作为不可信结构化 JSON；按截断后的规范输入 SHA-256 指纹更新，模型失败或输出逐轮复述时回退为确定性的主题/结论语义合并。
- 新增 `tour_reports.record_summary_source_hash` 迁移；未回答问题只更新报告统计，不触发摘要 LLM。POST/GET 报告共用限流，调用 LLM 前释放事务，返回后按 session→report 锁序重读最新状态，过期摘要不得覆盖并发的新事件、session 字段或较新报告。
- `record_events` 在查重与插入前锁定 session 行，预生成稳定事件 UUID，并把加锁、重查、重建和提交作为完整重试单元；即使提交结果不明也能按主键/client ID 收敛，离线补传不会重复。
- TTS 流式 PCM16 与文件 WAV 缓存按规范 JSON 模式键隔离；缓存和上游 WAV/PCM 均做格式校验。独立接口使用 token 哈希 30/min + 共享 IP 300/min 双层限流，无 token 时保留 IP 桶；文本、voice、style、persona 均加边界，失败日志不记录文本/token。
- 小程序聊天 message 去除首尾空白并要求 1–2000 字，纯空白在进入付费 LLM 前返回 422。
- 本轮定向组合验证 `230 passed`（7 条既有 warning）；最终全后端串行测试 `1124 passed, 23 skipped, 13 warnings`，跳过项均因本机未启动 PostgreSQL、Elasticsearch、Ollama 或 Redis。scoped Ruff、Alembic 单一 head `20260716_report_summary_hash` 与 `git diff --check` 通过。
