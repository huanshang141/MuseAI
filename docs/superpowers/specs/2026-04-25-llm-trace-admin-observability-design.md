# LLM 调用可观测性与审计入口设计文档（Admin Only）

## 1. 概述

本设计为 MuseAI 增加“每次 LLM 调用可查看”的系统级能力，目标是让开发者与运维在管理后台中可追溯每次调用的关键信息（请求 URL、模型、上下文、耗时、状态、错误），并以**人类可读**形式查看。

本设计已锁定以下业务决策：

1. 仅管理员可见。
2. 默认脱敏保存。
3. 覆盖系统内全部 LLM 调用（不仅聊天主链路）。

---

## 2. 背景与问题

当前系统已具备请求级 `request_id` 与聊天级 `trace_id`，但仍存在关键缺口：

1. 缺少结构化持久化：当前只保存对话消息，不保存 LLM 调用元数据与完整上下文。
2. 缺少统一采集点：调用散落于 `OpenAICompatibleProvider` 与 `LangChain ChatOpenAI` 两条路径。
3. 缺少审计入口：前端仅展示聊天消息 `trace_id` 文本，无详情入口。
4. 现有日志不可产品化复用：文件日志字段不稳定，且不适合权限化查询与筛选。

这导致出现线上问题时，需要依赖临时日志拼接排查，效率低、可追溯性差。

---

## 3. 目标与非目标

### 3.1 目标

1. 系统级覆盖：记录所有 LLM 调用（Provider 直连 + LangChain 调用）。
2. 安全可用：默认脱敏存储，禁止原文敏感数据泄漏。
3. 可查询：支持后台分页、筛选、详情查看。
4. 人类可读：详情中提供结构化视图 + 友好文本快照。
5. 可关联：打通 `request_id`、`trace_id` 与业务会话字段，支持链路回放。

### 3.2 非目标

1. 不对普通用户开放调用详情。
2. 不做实时监控面板（Grafana 类）替代。
3. 不在首版实现复杂的成本计费报表。
4. 不将审计数据直接暴露到聊天页面。

---

## 4. 需求拆解

### 4.1 必需字段

每次 LLM 调用必须至少包含：

1. 目标 URL（base_url + endpoint）。
2. 模型标识（model）。
3. 完整上下文（messages/prompt，脱敏后）。
4. 时序信息（开始、结束、耗时）。
5. 结果信息（成功/失败、错误摘要、token 用量）。
6. 链路信息（request_id、trace_id、source、session_id）。

### 4.2 权限要求

1. 所有查询接口仅管理员可访问。
2. 非管理员访问返回 403。
3. 前端入口仅出现在 admin 导航。

### 4.3 脱敏要求

1. 默认启用，且不可被前端关闭。
2. 对结构化 JSON 递归脱敏。
3. 对纯文本上下文执行正则脱敏。
4. 脱敏失败时不得回退为原文，使用安全占位文本。

---

## 5. 方案对比

### 方案 A：各业务点手工埋点

优点：
- 直观、改动范围可局部控制。

缺点：
- 漏埋风险高，无法保证“全量”。
- 后续新增调用点维护成本高。

### 方案 B：统一追踪层（推荐）

做法：
- 在 `OpenAICompatibleProvider` 与 `LangChain callback` 两个总入口集中采集。
- 统一通过 `LLMTraceRecorder` 异步入库。

优点：
- 覆盖完整、可扩展、长期维护成本低。

缺点：
- 首版需要额外基础设施。

### 方案 C：日志文件方案

优点：
- 上线快，不需迁移。

缺点：
- 权限控制、筛选、分页、链路关联都弱。
- 不适合管理后台产品化。

**结论：采用方案 B。**

---

## 6. 总体架构设计

### 6.1 架构图（逻辑）

```text
HTTP Request
  └─ RequestLoggingMiddleware (request_id)
      └─ Business Service (chat/tour/report/...)
          ├─ OpenAICompatibleProvider.generate/generate_stream
          │    └─ LLMTraceRecorder.record(...)
          └─ LangChain ChatOpenAI (callbacks)
               └─ LLMTraceCallbackHandler
                    └─ LLMTraceRecorder.record(...)

LLMTraceRecorder
  ├─ MaskingService (JSON + 文本脱敏)
  ├─ ReadableFormatter (人类可读快照)
  └─ Postgres LLMTraceEventRepository

Admin APIs
  ├─ GET /api/v1/admin/llm-traces
  └─ GET /api/v1/admin/llm-traces/{call_id}

Frontend Admin
  └─ /admin/llm-traces 列表 + 详情抽屉
```

### 6.2 采集覆盖矩阵

| 调用路径 | 当前入口 | 采集方式 | 备注 |
|---|---|---|---|
| 聊天流式生成 | `OpenAICompatibleProvider.generate_stream` | Provider 统一埋点 | 覆盖 `/chat/ask/stream`、`/chat/guest/message` |
| 查询改写 | `OpenAICompatibleProvider.generate` | Provider 统一埋点 | 覆盖 `ConversationAwareQueryRewriter` |
| RAG 生成 | `ChatOpenAI.ainvoke` | LangChain callback | 覆盖 `RAGAgent.generate` |
| 导览/策展链路中的 ChatOpenAI 调用 | `ChatOpenAI.*` | LangChain callback | 自动覆盖 |
| 导览报告单句生成 | `llm_provider.generate` | Provider 统一埋点 | 覆盖 `tour_report_service` |

---

## 7. 数据模型设计

新增表：`llm_trace_events`

### 7.1 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `VARCHAR(36)` | 主键 UUID |
| `call_id` | `VARCHAR(64)` | 单次调用唯一标识（可读） |
| `request_id` | `VARCHAR(64)` | HTTP 请求级关联 ID |
| `trace_id` | `VARCHAR(64)` | 业务 trace（聊天/导览） |
| `source` | `VARCHAR(64)` | 来源枚举：`chat_stream`/`guest_chat`/`query_rewrite`/`rag_generate`/`tour_report`/... |
| `endpoint_method` | `VARCHAR(10)` | HTTP 方法（若存在） |
| `endpoint_path` | `VARCHAR(255)` | HTTP 路径（若存在） |
| `actor_type` | `VARCHAR(20)` | `admin`/`user`/`guest`/`system` |
| `actor_id` | `VARCHAR(64)` | 用户 ID 或 guest 标识 |
| `session_type` | `VARCHAR(20)` | `chat`/`tour`/`none` |
| `session_id` | `VARCHAR(64)` | 业务会话 ID |
| `provider` | `VARCHAR(64)` | `openai-compatible`/`langchain-openai` |
| `base_url` | `TEXT` | 请求目标基础 URL（脱敏后） |
| `model` | `VARCHAR(128)` | 模型名 |
| `request_payload_masked` | `JSONB` | 脱敏后的请求体 |
| `response_payload_masked` | `JSONB` | 脱敏后的响应体 |
| `request_readable` | `TEXT` | 人类可读请求快照 |
| `response_readable` | `TEXT` | 人类可读响应快照 |
| `prompt_tokens` | `INTEGER` | 输入 token |
| `completion_tokens` | `INTEGER` | 输出 token |
| `total_tokens` | `INTEGER` | 总 token |
| `started_at` | `TIMESTAMPTZ` | 开始时间 |
| `ended_at` | `TIMESTAMPTZ` | 结束时间 |
| `duration_ms` | `INTEGER` | 耗时 |
| `status` | `VARCHAR(20)` | `success`/`error` |
| `error_type` | `VARCHAR(128)` | 错误类型 |
| `error_message_masked` | `TEXT` | 脱敏错误信息 |
| `created_at` | `TIMESTAMPTZ` | 创建时间（默认 now） |

### 7.2 索引

1. `ix_llm_traces_created_at` (`created_at DESC`)
2. `ix_llm_traces_trace_id` (`trace_id`)
3. `ix_llm_traces_request_id` (`request_id`)
4. `ix_llm_traces_source_status` (`source`, `status`)
5. `ix_llm_traces_model` (`model`)
6. `ix_llm_traces_session_id` (`session_id`)
7. `uq_llm_traces_call_id` (`call_id` unique)

---

## 8. 脱敏策略设计（默认开启）

### 8.1 规则范围

对以下信息进行掩码：

1. 凭证类：`api_key`、`token`、`secret`、`authorization`、`password`。
2. 身份类：邮箱、手机号、身份证风格数字串。
3. 长随机串：长度超过阈值且满足 token 特征的字符串。

### 8.2 JSON 脱敏

1. 递归处理对象、数组、字符串。
2. 命中敏感 key 时，值替换为 `[REDACTED]`。
3. 保留结构，不破坏字段层次，便于诊断。

### 8.3 文本脱敏

1. 正则替换邮箱、手机号、Bearer/JWT。
2. 对 URL query 参数中的敏感键脱敏。

### 8.4 失败兜底

1. 脱敏函数抛错时，不写原文。
2. 写入 `"[MASKING_FAILED]"` 占位，并记录内部告警日志。

---

## 9. 追踪上下文设计

通过 `contextvars` 维护当前调用上下文（线程/协程安全）：

字段建议：

1. `request_id`
2. `trace_id`
3. `source`
4. `endpoint_method`
5. `endpoint_path`
6. `actor_type`
7. `actor_id`
8. `session_type`
9. `session_id`

写入时优先级：

1. 显式参数
2. `contextvars` 值
3. 空值（允许）

---

## 10. API 设计（Admin）

### 10.1 列表接口

`GET /api/v1/admin/llm-traces`

查询参数：

1. `limit`（默认 20，最大 100）
2. `offset`（默认 0）
3. `source`（可选）
4. `model`（可选）
5. `status`（可选）
6. `trace_id`（可选）
7. `start_at` / `end_at`（可选）

返回字段（摘要）：

1. `call_id`
2. `created_at`
3. `source`
4. `model`
5. `duration_ms`
6. `total_tokens`
7. `status`
8. `trace_id`
9. `request_id`

### 10.2 详情接口

`GET /api/v1/admin/llm-traces/{call_id}`

返回字段：完整事件记录，包含：

1. `request_payload_masked`
2. `response_payload_masked`
3. `request_readable`
4. `response_readable`
5. 错误信息、token、链路字段。

### 10.3 权限

沿用当前 admin 依赖注入方式：`CurrentAdminUser`。

---

## 11. 前端设计（Admin 入口）

### 11.1 路由与导航

1. 新增子路由：`/admin/llm-traces`。
2. 在 `AdminNavSidebar` 增加菜单项“LLM 调用记录”。

### 11.2 页面结构

1. 筛选条：来源、模型、状态、时间区间、trace_id。
2. 表格：时间、来源、模型、耗时、tokens、状态、trace_id。
3. 详情抽屉：
   - 基本信息卡
   - 请求可读区块（`request_readable`）
   - 响应可读区块（`response_readable`）
   - 原始脱敏 JSON（可复制）

### 11.3 视觉要求

1. 复用现有 design-system token。
2. 信息层次清晰，避免一次性展示过长 JSON。
3. 移动端下详情抽屉改全屏。

---

## 12. 错误处理与降级

1. 记录失败不影响主业务响应（审计“旁路”原则）。
2. 入库失败仅记录 `warning`，不抛给用户。
3. 前端详情获取失败时显示“记录不可用”，不阻断列表浏览。

---

## 13. 测试策略

### 13.1 后端单元测试

1. `MaskingService`：敏感字段与文本替换。
2. `LLMTraceRecorder`：成功/异常/脱敏失败兜底。
3. Provider 埋点：`generate`/`generate_stream` 正常与异常路径。
4. LangChain callback：触发开始/结束事件并形成完整记录。

### 13.2 后端契约测试

1. Admin 列表与详情接口返回结构稳定。
2. 非 admin 访问返回 403。
3. 筛选条件行为正确。

### 13.3 前端测试

1. 路由守卫下 admin 页面可达性。
2. 筛选与分页交互。
3. 详情抽屉渲染与空态。

---

## 14. 迁移与上线策略

1. 先部署 migration（向后兼容，不影响旧功能）。
2. 后端上线追踪逻辑（先灰度到开发环境）。
3. 验证采集量与字段完整性。
4. 前端 admin 页面上线。
5. 观察 24-48 小时后启用更严格告警阈值。

---

## 15. 风险与对策

1. 风险：全量记录导致存储增长快。  
   对策：首版限制保留周期（例如 30 天）并加清理脚本。
2. 风险：流式调用响应体过长。  
   对策：保留完整脱敏文本 + 摘要字段；必要时增加截断策略与标记位。
3. 风险：callback 与 provider 双重记录。  
   对策：通过 `provider` + `source` 区分，允许并行存在；后续可引入聚合视图。

---

## 16. 验收标准

满足以下条件视为设计验收通过：

1. 管理员可在后台查看所有 LLM 调用列表与详情。
2. 每条记录可看到 URL、模型、完整上下文（脱敏后）与状态耗时。
3. 非管理员无法访问接口与页面。
4. 覆盖 `OpenAICompatibleProvider` 与 `ChatOpenAI` 两条调用路径。
5. 脱敏规则有自动化测试覆盖，且失败不泄漏原文。

