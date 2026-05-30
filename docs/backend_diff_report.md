# Backend Development Report

> 生成日期：2026-05-30
> 本报告记录接手项目后对 MuseAI 后端所做的全部改动。

---

## 项目背景

MuseAI 是半坡博物馆 AI 智慧导览系统，后端采用 FastAPI + LangGraph 架构，核心为六步 RAG 流水线（rewrite → retrieve → merge → rerank → filter → evaluate → generate）。接手时后端已具备完整的 Persona 体系、Session 管理、游览事件记录和报告生成能力，但存在以下问题：

1. **RAG 管道存在重复 LLM 调用**：`generate` 节点内部会调用一次 LLM 生成答案，但 `tour_chat_service.py` 随后又通过 `llm_provider.generate_stream()` 再次调用 LLM 做流式输出，两次调用中第一次的结果被完全丢弃——每请求浪费 10-25 秒。
2. **无全链路性能日志**：首次 token 延迟普遍达到 1-2 分钟，但没有任何结构化埋点可用于定位瓶颈所在（rewrite? retrieve? generate?）。
3. **trace_id 创建时机偏晚**：trace_id 在 session 加载后才创建，前几个阶段的日志无法绑定同一 trace。

---

## 对比基线

| 项目 | 值 |
|------|---|
| 对比基线 commit | `c6c62ab86df6cc6aa308821810fb5388e1f7d138` |
| 基线来自 | `upstream/main`（huanshang141/MuseAI.git） |
| 当前分支 | `stage9`（本地）|
| 当前 HEAD | `199ce41` |
| 基线日期 | 接手时拉取 upstream/main |

---

## 提交历史

```
a524437  chore: add AI latency diagnostics
199ce41  perf: skip duplicate RAG generate step in tour chat
```

两个提交，实现一个完整的优化闭环：先诊断（埋点），后优化（skip_generate）。

---

## 修改文件清单

| 文件 | 类型 | 变动行数 |
|------|------|---------|
| `backend/app/application/tour_chat_service.py` | 修改 | +93 |
| `backend/app/infra/langchain/agents.py` | 修改 | +214 / -154（重构+注释清理） |
| `docs/ai_latency_diagnostics.md` | 新增 | +254 |

**共 3 个文件，561 行新增，154 行删除。**

> **注意**：`backend/app/application/tour_chat_service.py` 当前有 1 处工作区未提交修改（`git status` 显示 ` M`），建议 review 后决定是否纳入下次提交。

---

## API 变化

**无 API 接口改动。**

所有修改均在内部服务层，对外的 REST 端点、请求/响应 Schema、SSE 事件格式均未变化，前端无需任何适配。

---

## Prompt / RAG 变化

### skip_generate：消除重复 LLM 调用

这是本次最核心的优化。

**原有流程（有 bug）**：

```
rag_agent.run(message, system_prompt)
  └─ generate 节点: LLM.generate(prompt)   ← 完整 LLM 调用，耗时 10-25 秒
                    result["answer"] = ...  ← 这个结果从未被用到
_stream_rag:
  └─ llm_provider.generate_stream(...)     ← 又一次 LLM 调用（流式）
  └─ yield chunk → 前端显示
```

第一次 LLM 调用的输出 `result["answer"]` 在 `_stream_rag` 中完全被忽略，纯粹浪费。

**修复后流程**：

```
rag_agent.run(message, system_prompt, skip_generate=True)
  └─ generate 节点: skip_generate=True → 直接返回 {"answer": ""}
                    耗时 < 1ms（无 LLM 调用）
_stream_rag:
  └─ llm_provider.generate_stream(...)     ← 唯一的 LLM 调用（流式）
  └─ yield chunk → 前端显示
```

**改动范围**：
- `RAGState` TypedDict 新增 `skip_generate: bool` 字段
- `RAGAgent.run()` 接受 `skip_generate` 参数并注入状态
- `generate` 节点内：`if state.get("skip_generate"): return {"answer": ""}` 短路
- `_stream_rag()` 调用 `rag_agent.run()` 时传入 `skip_generate=True`

**预期效果**：每次 tour 聊天请求减少 10-25 秒延迟（取决于模型和上下文长度）。

---

## 性能优化

### 全链路结构化性能埋点

在 `tour_chat_service.py` 和 `agents.py` 中添加了系统性的 `[perf]` 日志，覆盖 RAG 流水线每个节点。

**日志格式**（loguru structured logging）：

```
[perf] session_loaded    duration_ms=11ms   ok=True
[perf] style_parsed      ok=True
[perf] tts_config        skipped=True
[perf] rewrite           duration_ms=0ms    ok=True
[perf] retrieve          duration_ms=1800ms ok=True
[perf] merge             duration_ms=120ms  ok=True   parents_replaced=2
[perf] rerank            duration_ms=450ms  ok=True
[perf] filter            duration_ms=2ms    ok=True
[perf] evaluate          duration_ms=1ms    ok=True
[perf] rag_pipeline      duration_ms=2400ms ok=True
[perf] prompt_build      duration_ms=8ms    ok=True
[perf] llm_stream_start
[perf] first_token       elapsed_ms=3200ms
[perf] llm_stream        duration_ms=14300ms ok=True
[perf] stream_done       duration_ms=14320ms ok=True
[perf] total             duration_ms=14350ms ok=True
```

所有日志携带 `perf=True` 字段，便于过滤：

```bash
grep '"perf": true' logs/app.log | tail -30
# 或文本模式：
grep '\[perf\]' logs/app.log | tail -30
```

**埋点位置汇总**：

| 埋点 | 位置 | 说明 |
|------|------|------|
| `session_loaded` | `tour_chat_service.py` | Session 查询耗时 |
| `style_parsed` | `tour_chat_service.py` | 同步，可忽略 |
| `tts_config` | `tour_chat_service.py` | TTS 配置获取耗时，或 skipped |
| `rewrite` | `agents.py` | query rewrite 节点（try/finally 保障） |
| `retrieve` | `agents.py` | ES 向量检索耗时 |
| `merge` | `agents.py` | 层级 chunk 合并耗时，含 `parents_replaced` |
| `rerank` | `agents.py` | Reranker 耗时 |
| `filter` | `agents.py` | 动态过滤节点耗时 |
| `evaluate` | `agents.py` | 质量评估节点耗时 |
| `rag_pipeline` | `tour_chat_service.py` | 整个 `rag_agent.run()` 总耗时 |
| `prompt_build` | `tour_chat_service.py` | Prompt Gateway 渲染耗时 |
| `llm_stream_start` | `tour_chat_service.py` | LLM 开始流式输出的时间戳 |
| `first_token` | `tour_chat_service.py` | 从 RAG 开始到第一个 chunk 的延迟 |
| `llm_stream` | `tour_chat_service.py` | LLM 流式输出总耗时 |
| `stream_done` | `tour_chat_service.py` | 整个 stream 完成耗时 |
| `total` | `tour_chat_service.py` | 从请求入口到 done 的总耗时 |

### trace_id 提前创建

将 `trace_id = str(uuid.uuid4())` 从 Session 加载之后移动到函数入口处，使 session_loaded、style_parsed 等早期阶段的日志也能绑定到同一 trace_id，便于关联查询。

### `_perf()` 辅助方法（agents.py）

新增 `RAGAgent._perf(stage, duration_ms, ok, **extra)` 统一方法，所有 RAG 节点通过此方法发日志，避免重复代码。`_perf_trace_id` 由 `run()` 调用前通过 `set_trace_id()` 注入。

---

## LLM / Embedding / Rerank / TTS 配置

**全部为配置级别改动，无代码修改。** 后端使用 provider-agnostic 架构，通过 `.env` 切换所有外部服务。

### LLM：DeepSeek

| 环境变量 | 值 |
|---------|---|
| `LLM_PROVIDER` | `openai_compatible` |
| `LLM_BASE_URL` | `https://api.deepseek.com` |
| `LLM_MODEL` | `deepseek-v4-flash` |
| `LLM_API_KEY` | *(已在 `.env` 中配置，不入版本库)* |
| `LLM_HEADERS` | `{"User-Agent":"curl/8.5.0"}` |

`OpenAICompatibleProvider` 使用 `openai` SDK 的 `AsyncOpenAI(base_url=..., api_key=...)` 初始化，与 DeepSeek OpenAI-compatible 接口完全兼容，无需任何代码改动。

> **注意**：`deepseek-chat` / `deepseek-reasoner` 将于 2026/07/24 废弃，当前使用 `deepseek-v4-flash` 已对应新版模型。

### Embedding：SiliconFlow / Qwen3

| 环境变量 | 值 |
|---------|---|
| `EMBEDDING_PROVIDER` | `openai`（OpenAI-compatible 模式） |
| `EMBEDDING_OPENAI_BASE_URL` | `https://api.siliconflow.cn/v1` |
| `EMBEDDING_OPENAI_MODEL` | `Qwen/Qwen3-Embedding-8B` |
| `EMBEDDING_DIMS` | `4096` |
| `ELASTICSEARCH_INDEX` | `museai_chunks_v1` |

原 Ollama 本地 embedding 已替换为 SiliconFlow 云端 Qwen3 embedding，向量维度 4096，ES 索引 `museai_chunks_v1`。

### Rerank：SiliconFlow / BGE

| 环境变量 | 值 |
|---------|---|
| `RERANK_PROVIDER` | `siliconflow` |
| `RERANK_BASE_URL` | `https://api.siliconflow.cn` |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` |
| `RERANK_TOP_N` | `10` |

### TTS：Xiaomi / 冰糖

| 环境变量 | 值 |
|---------|---|
| `TTS_ENABLED` | `true` |
| `TTS_PROVIDER` | `xiaomi` |
| `TTS_DEFAULT_VOICE` | `冰糖` |

TTS 已在服务器上启用，前端（`stage9`）尚未接入播放逻辑。

---

### 部署状态说明

| 位置 | 分支 | 说明 |
|------|------|------|
| 服务器 | `stage8` | 当前线上运行版本，已含 DeepSeek + SiliconFlow 配置 |
| 本地开发 | `stage9` | 包含 `skip_generate` 优化 + 全链路 perf 日志，**尚未部署** |

`stage9` 的两个核心改动（消除重复 LLM 调用、结构化性能埋点）在 DeepSeek 环境下同样有效，部署后可直接使用。

---

## Persona 体系

**无变化。** Persona（A/B/C）体系由基线版本已完整实现，本阶段未触碰 `build_system_prompt`、Persona 路由逻辑或任何 Prompt 模板。

---

## Context 体系

**无变化。** Exhibit context（展品上下文注入）在基线版本已支持，`tour_chat_service.py` 的 `exhibit_context` 参数路径未修改。

---

## Bug 修复

| # | 问题 | 修复方式 | 影响 |
|-|-|-|-|
| 1 | RAG generate 节点与 `_stream_rag` 中 `llm_provider.generate_stream` 构成重复 LLM 调用，第一次调用结果被丢弃 | 引入 `skip_generate=True` 让 generate 节点短路，仅保留流式调用 | 消除每请求 10-25 秒的无效等待 |

---

## 测试建议

### 核心功能验证

1. **skip_generate 正确性**：发送一条 tour 聊天消息，验证前端仍能正常收到 SSE chunk，`done` 事件包含完整内容。
2. **性能改善**：对比 skip_generate 前后的 `[perf] total duration_ms`，应下降约 10-25 秒。
3. **perf 日志完整性**：一次请求后，`grep '\[perf\]' logs/app.log | tail -20` 应能看到上表所有阶段的日志（`rewrite` 可能因无历史上下文而耗时 0ms）。

### 回归验证

- RAG 检索结果质量不应下降（`skip_generate` 不影响 retrieve/rerank/filter 节点）
- 报告生成仍正常（报告 API 不经过本次修改的路径）
- TTS（如果启用）仍正常接收 `tts_config`

### 性能基准

使用 `first_token elapsed_ms` 指标：

| 阶段 | 正常范围 | 异常阈值 |
|------|---------|---------|
| `rewrite` | 0-500ms（有历史时）| > 2000ms |
| `retrieve` | 200-2000ms | > 5000ms（Ollama embedding 超时）|
| `rerank` | 200-800ms | > 2000ms |
| `rag_pipeline` | 500-3000ms | > 6000ms |
| `first_token` | 1000-5000ms | > 10000ms（基线后有 skip_generate 应大幅改善）|

---

## 部署注意事项

1. **无需数据库迁移**：本次改动不涉及 Schema 变化。
2. **无需依赖更新**：仅新增了 Python 标准库 `import time`，无新外部包。
3. **无需前端改动**：API 接口、SSE 事件格式完全兼容。
4. **`.env` 配置**：确保部署环境中设置 `LLM_BASE_URL=https://api.deepseek.com`（无 `/v1` 后缀）、`LLM_MODEL=deepseek-v4-flash` 及对应 API Key。Embedding/Rerank 配置见上方"LLM / Embedding / Rerank / TTS 配置"章节。`.env` 不入版本库，需在部署机器上手动维护。
5. **日志量增加**：每次 tour chat 请求新增约 15 行 `[perf]` 结构化日志，如日志存储有成本约束，可通过 `log.bind(perf=True)` 过滤字段控制输出级别。
6. **未提交的工作区修改**：`backend/app/application/tour_chat_service.py` 存在 1 处未 staged 的改动，部署前确认是否需要一并提交。

---

## 参考文档

- `backend/docs/ai_latency_diagnostics.md`：AI 延迟全链路诊断手册（本次新增），包含每个慢阶段的排查流程和推荐优化优先级（P0: 移除 generate 节点 LLM 调用 → 已完成；P1: query rewrite 可选关闭；P2: Ollama embedding 保活；P3: rerank top_n 调低）。
