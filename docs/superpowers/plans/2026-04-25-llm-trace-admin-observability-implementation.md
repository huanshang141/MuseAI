# LLM 调用可观测性与审计入口实施计划（Admin Only）

> **Goal:** 在 MuseAI 中落地“系统内全部 LLM 调用可追踪、默认脱敏、仅管理员可见”的完整能力。  
> **Scope:** 后端采集 + 存储 + Admin API + 前端管理页 + 测试与验证。  
> **Constraint:** 不影响现有业务链路可用性，审计记录失败不得阻断主流程。

---

## 0. 任务总览

### 0.1 交付物

1. 设计文档（已完成）：`docs/superpowers/specs/2026-04-25-llm-trace-admin-observability-design.md`
2. 实施计划（本文件）
3. 代码交付：数据库、后端采集、Admin API、前端页面、测试

### 0.2 执行顺序

1. 数据层与模型
2. 追踪基础设施（脱敏、记录器、上下文）
3. 全调用路径接入（Provider + LangChain）
4. Admin API
5. 前端 Admin 页面
6. 测试与回归
7. 文档与验收

---

## 1. 文件改动清单（目标）

### 1.1 Backend 新增文件

1. `backend/app/infra/postgres/models/llm_trace.py`
2. `backend/alembic/versions/20260425_add_llm_trace_events.py`
3. `backend/app/application/llm_trace/masking.py`
4. `backend/app/application/llm_trace/formatter.py`
5. `backend/app/application/llm_trace/context.py`
6. `backend/app/application/llm_trace/recorder.py`
7. `backend/app/application/llm_trace/repository.py`
8. `backend/app/infra/langchain/llm_trace_callback.py`
9. `backend/app/api/admin/llm_traces.py`
10. `backend/tests/unit/test_llm_trace_masking.py`
11. `backend/tests/unit/test_llm_trace_recorder.py`
12. `backend/tests/contract/test_admin_llm_traces_api.py`

### 1.2 Backend 修改文件

1. `backend/app/infra/postgres/models/__init__.py`
2. `backend/app/domain/entities.py`（若需要领域实体）
3. `backend/app/infra/providers/llm.py`
4. `backend/app/infra/langchain/__init__.py`
5. `backend/app/main.py`
6. `backend/app/api/admin/__init__.py`

### 1.3 Frontend 新增文件

1. `frontend/src/components/admin/LLMTraceManager.vue`
2. `frontend/src/components/admin/__tests__/LLMTraceManager.test.js`

### 1.4 Frontend 修改文件

1. `frontend/src/router/index.js`
2. `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`
3. `frontend/src/api/index.js`

---

## 2. 实施步骤（逐步可执行）

## Task 1: 建立数据库模型与迁移

**目标：** 提供可查询的结构化审计存储。

- [ ] Step 1: 新增 ORM 模型文件

创建 `backend/app/infra/postgres/models/llm_trace.py`，定义 `LLMTraceEvent`。

关键字段：

1. `call_id`, `request_id`, `trace_id`, `source`
2. `endpoint_method`, `endpoint_path`, `actor_type`, `actor_id`, `session_id`
3. `provider`, `base_url`, `model`
4. `request_payload_masked`, `response_payload_masked`
5. `request_readable`, `response_readable`
6. `prompt_tokens`, `completion_tokens`, `total_tokens`
7. `started_at`, `ended_at`, `duration_ms`, `status`, `error_type`, `error_message_masked`

- [ ] Step 2: 导出模型

修改 `backend/app/infra/postgres/models/__init__.py`，加入 `LLMTraceEvent` 导出。

- [ ] Step 3: 新增 Alembic 迁移

创建 `backend/alembic/versions/20260425_add_llm_trace_events.py`。

要求：

1. 创建 `llm_trace_events` 表。
2. 创建索引与唯一约束（`uq_call_id`）。
3. `downgrade` 可回滚。

- [ ] Step 4: 迁移验证

```bash
cd /home/singer/MuseAI
uv run alembic -c backend/alembic.ini upgrade head
```

预期：迁移成功，无异常。

- [ ] Step 5: 模型导入验证

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_db_models.py -q
```

预期：模型层测试通过。

---

## Task 2: 实现脱敏与可读格式化基础设施

**目标：** 默认脱敏 + 人类可读文本。

- [ ] Step 1: 创建脱敏服务

创建 `backend/app/application/llm_trace/masking.py`。

提供 API：

1. `mask_json(data: Any) -> Any`
2. `mask_text(text: str) -> str`
3. `mask_url(url: str) -> str`

最低规则：

1. key 命中：`token|secret|password|api_key|authorization`
2. 邮箱掩码
3. 手机号掩码
4. Bearer/JWT 掩码

- [ ] Step 2: 创建可读格式化器

创建 `backend/app/application/llm_trace/formatter.py`。

提供 API：

1. `to_readable_request(masked_payload) -> str`
2. `to_readable_response(masked_payload) -> str`

要求：

1. 保留关键信息层级（模型、消息、参数、token、状态）。
2. 控制文本长度并标注截断。

- [ ] Step 3: 单元测试

创建 `backend/tests/unit/test_llm_trace_masking.py`。

覆盖：

1. JSON 递归脱敏
2. 文本脱敏
3. URL 查询参数脱敏
4. 脱敏异常兜底（不得返回原文）

执行：

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_llm_trace_masking.py -q
```

---

## Task 3: 实现追踪上下文与记录器

**目标：** 解耦业务与存储，记录失败不影响主流程。

- [ ] Step 1: 上下文模块

创建 `backend/app/application/llm_trace/context.py`。

内容：

1. `ContextVar` 保存 `request_id/trace_id/source/endpoint/actor/session`。
2. `set_trace_context(...)` 上下文管理器。
3. `get_trace_context()` 读取当前上下文。

- [ ] Step 2: 仓储层

创建 `backend/app/application/llm_trace/repository.py`。

内容：

1. `create_event(event_data)`
2. `list_events(filters, limit, offset)`
3. `count_events(filters)`
4. `get_by_call_id(call_id)`

- [ ] Step 3: 记录器

创建 `backend/app/application/llm_trace/recorder.py`。

内容：

1. `record_call_start(...)`
2. `record_call_success(...)`
3. `record_call_error(...)`
4. `record_call_once(...)`（直接写完整记录）

要求：

1. 内部统一调用 `MaskingService + Formatter + Repository`。
2. 异常只记录日志，不向上抛出。

- [ ] Step 4: 单元测试

创建 `backend/tests/unit/test_llm_trace_recorder.py`。

覆盖：

1. 成功记录
2. 错误记录
3. 脱敏失败兜底
4. repository 异常不影响主流程

执行：

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_llm_trace_recorder.py -q
```

---

## Task 4: 接入 OpenAICompatibleProvider（全局直连路径）

**目标：** 覆盖所有经 `OpenAICompatibleProvider` 的调用。

- [ ] Step 1: 扩展 provider 属性

修改 `backend/app/infra/providers/llm.py`：

1. 保存 `self.base_url`。
2. 接受可选 `trace_recorder`。

- [ ] Step 2: 在 `generate` 中埋点

记录：

1. 请求（model + messages）
2. 响应（content + usage）
3. 耗时与状态

- [ ] Step 3: 在 `generate_stream` 中埋点

策略：

1. 聚合 chunk 为完整响应后写一条记录。
2. 记录流式总耗时、总长度、异常状态。

- [ ] Step 4: 测试

扩展 `backend/tests/unit/test_llm_provider.py`，新增断言：

1. recorder 被调用。
2. error 路径也被记录。

执行：

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_llm_provider.py -q
```

---

## Task 5: 接入 LangChain ChatOpenAI（RAG 等路径）

**目标：** 覆盖所有经 `ChatOpenAI` 的调用。

- [ ] Step 1: 新增 callback handler

创建 `backend/app/infra/langchain/llm_trace_callback.py`，实现异步回调：

1. `on_llm_start`
2. `on_llm_end`
3. `on_llm_error`

记录字段：

1. prompts/messages
2. model/provider/base_url
3. usage metadata（如可得）

- [ ] Step 2: 修改 `create_llm`

修改 `backend/app/infra/langchain/__init__.py`：

1. `create_llm(settings, callbacks=None)`。
2. 把 callback 注入 `ChatOpenAI`。

- [ ] Step 3: main 初始化注入

修改 `backend/app/main.py`：

1. 初始化 `LLMTraceRecorder`。
2. 创建 callback handler。
3. `create_llm` 注入 callback。
4. `OpenAICompatibleProvider.from_settings` 注入 recorder。

- [ ] Step 4: 回归验证

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_factory_functions.py -q
uv run pytest backend/tests/unit/test_request_id_bridge.py -q || true
```

说明：第二条若路径不存在，用对应现有测试替换并补新用例。

---

## Task 6: 构建 Admin 查询 API

**目标：** 提供管理员列表/详情接口。

- [ ] Step 1: 新建 admin router

创建 `backend/app/api/admin/llm_traces.py`：

接口：

1. `GET /admin/llm-traces`
2. `GET /admin/llm-traces/{call_id}`

要求：

1. 使用 `CurrentAdminUser`。
2. 支持分页与筛选（source/model/status/trace_id/time range）。

- [ ] Step 2: 注册路由

修改：

1. `backend/app/api/admin/__init__.py` 导出新 router。
2. `backend/app/main.py` include router。

- [ ] Step 3: 契约测试

创建 `backend/tests/contract/test_admin_llm_traces_api.py`。

覆盖：

1. 401（未登录）
2. 403（非 admin）
3. 200（admin 列表与详情）
4. 筛选参数生效

执行：

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/contract/test_admin_llm_traces_api.py -q
```

---

## Task 7: 前端 Admin 页面与入口

**目标：** 提供“美观易读”的后台入口。

- [ ] Step 1: API 客户端扩展

修改 `frontend/src/api/index.js`：

新增：

1. `api.admin.llmTraces.list(params)`
2. `api.admin.llmTraces.detail(callId)`

- [ ] Step 2: 路由接入

修改 `frontend/src/router/index.js`，新增子路由：

1. `path: 'llm-traces'`
2. `name: 'admin-llm-traces'`
3. `component: () => import('../components/admin/LLMTraceManager.vue')`

- [ ] Step 3: 侧边栏菜单

修改 `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`，新增菜单项：

1. `path: '/admin/llm-traces'`
2. `label: 'LLM 调用记录'`

- [ ] Step 4: 页面实现

创建 `frontend/src/components/admin/LLMTraceManager.vue`：

模块：

1. 筛选栏
2. 表格摘要
3. 详情抽屉（可读块 + JSON 块 + 复制）

- [ ] Step 5: 前端测试

创建 `frontend/src/components/admin/__tests__/LLMTraceManager.test.js`。

覆盖：

1. 列表加载
2. 筛选参数
3. 打开详情
4. 错误空态

执行：

```bash
cd /home/singer/MuseAI/frontend
npm run test -- LLMTraceManager
npm run build
```

---

## Task 8: 全链路验证与质量门禁

**目标：** 证明“全部 LLM 调用可追踪 + 仅 admin 可见 + 默认脱敏”。

- [ ] Step 1: 后端核心回归

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/unit/test_llm_provider.py backend/tests/unit/test_query_transform.py backend/tests/unit/test_tour_report_service.py -q
```

- [ ] Step 2: API 回归

```bash
cd /home/singer/MuseAI
uv run pytest backend/tests/contract/test_chat_api.py backend/tests/contract/test_prompts_api.py backend/tests/contract/test_admin_llm_traces_api.py -q
```

- [ ] Step 3: 端到端手验（开发环境）

1. 用 admin 登录系统。
2. 触发三类调用：聊天、导览、报告。
3. 打开 `/admin/llm-traces`，确认三类 source 均有记录。
4. 抽查上下文，确认敏感字段已脱敏。

- [ ] Step 4: Lint 与类型检查

```bash
cd /home/singer/MuseAI
uv run ruff check backend/
uv run mypy backend/
cd /home/singer/MuseAI/frontend
npm run lint
```

---

## Task 9: 文档与运维补充

**目标：** 提供可维护的后续运行说明。

- [ ] Step 1: 更新 README（管理功能说明）

补充：

1. Admin LLM Trace 页面用途
2. 仅管理员可见
3. 默认脱敏说明

- [ ] Step 2: 新增运维文档（建议）

创建 `docs/security/llm-trace-data-policy.md`，写明：

1. 字段定义
2. 脱敏策略
3. 保留周期
4. 数据访问权限

- [ ] Step 3: 清理策略脚本（可选但推荐）

创建 `scripts/cleanup_llm_traces.py`，支持：

1. `--days 30`
2. 定时清理过期审计数据

---

## 3. 验收清单（最终）

- [ ] 管理后台出现“LLM 调用记录”菜单与页面。
- [ ] 非 admin 用户无法访问 API/页面。
- [ ] 列表支持分页与筛选。
- [ ] 详情可看到 URL、模型、完整上下文（脱敏后）。
- [ ] Provider 与 LangChain 路径都有记录。
- [ ] 记录失败不影响主业务响应。
- [ ] 自动化测试通过。

---

## 4. 建议提交策略（可选）

1. `feat(db): add llm_trace_events table and model`
2. `feat(backend): add llm trace masking and recorder`
3. `feat(backend): instrument provider and langchain callbacks`
4. `feat(api): add admin llm traces endpoints`
5. `feat(frontend): add admin llm trace manager page`
6. `test: add llm trace unit and contract tests`
7. `docs: add llm trace observability spec and implementation plan`

