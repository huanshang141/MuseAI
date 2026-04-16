# MuseAI 中期技术债务审计报告

**日期**: 2026-04-17
**范围**: 全量 360° 扫描（代码质量 / 架构 / 测试 / 安全 / 性能与运维 / 文档与依赖）
**方法**: 主线程顺序扫描 + `ruff` / `mypy` / `pytest` / `npm audit` / `uv pip list --outdated` 静态验证
**基线**: 不与前次审计对比（用户指定，本次为独立审查）
**相关文档**:
- 后续整改 Design Spec: `docs/superpowers/specs/2026-04-17-midterm-debt-remediation-design.md`

---

## Executive Summary

MuseAI 当前代码库呈现"**强基础 + 局部债务**"的特征。严格分层的领域模型、零 TODO/FIXME、零 skipped test、集中化的安全基础（bcrypt / JWT / HttpOnly cookies / trusted-proxy XFF / 错误消息 sanitizer / 原子限流）、合理的缓存与索引策略，都在中等项目中属于上游水平。

但是在快速推进 tour / curator / admin / prompt management 等特性之后，积累了以下几个需要**本轮集中偿还**的结构性与运维债务：

**最重要的 5 项**：
1. **`infra/langchain/` 反向依赖 `application/`**（6 处）——违反 CLAUDE.md 声明的分层规则
2. **双重并行 Port 系统**（`domain/repositories.py` vs `application/ports/repositories.py`）——方向不清、签名漂移
3. **`mypy` 完全未运行**（`Source file found twice` 致早退）——所有 PR 的类型检查实际无效
4. **`chat_stream_service` 无单元测试** + 6 个其他 application 服务零测试覆盖
5. **vite 高危 CVE**（路径遍历，GHSA-4w7w-66w2-5vf9）+ 另有 2 个 moderate

**次重要 5 项**：
6. `verify_token` 未校验 token `type` 字段（如未来签发 refresh，可被当 access 用）
7. CLAUDE.md 严重过时（router 少列 6 个、env vars 少列 13 个）
8. SSE 事件字符串在 18+ 处复制粘贴（`f"data: {json.dumps(...)}\n\n"`）
9. `tour_chat_service.py:94` 异常分支同时发 `error` 和 `done`，契约模糊
10. `exhibit_service.list_exhibits` 无过滤分支下加载全表再 Python 切片

### 统计汇总

| 维度 | P0 | P1 | P2 | P3 | 小计 |
|---|---|---|---|---|---|
| 代码质量 | 0 | 3 | 5 | ~30 | ~38 |
| 架构 | 0 | 3 | 4 | ~5 | ~12 |
| 测试 | 1 | 4 | 4 | ~3 | ~12 |
| 安全 | 0 | 4 | 5 | 3 | 12 |
| 性能与运维 | 0 | 3 | 5 | 4 | 12 |
| 文档与依赖 | 0 | 4 | 3 | 3 | 10 |
| **合计** | **1** | **21** | **26** | **~48** | **~96** |

> P0 = 生产稳定性 / 正确性风险；P1 = 高成本或系统性债务；P2 = 中等影响；P3 = 细节

---

## 项目现状快照

### 规模
- Backend: **86** Python 文件 / **12,870** LOC（按层：api 3097, application 3438, domain 477, infra 4547, workflows 628）
- Frontend: **62** Vue/TS 文件 / **6,969** LOC
- Tests: **83** 测试文件 / **768** 测试用例（unit 63, contract 12, e2e 3, integration 2, architecture 2, performance 1）
- Migrations: **5** Alembic 文件
- Dependencies: Python ~50 顶层依赖 / Frontend 11 顶层依赖

### 静态检查基线
- **Ruff**: 36 errors（集中在 `tests/performance/*` 与 migration 脚本；核心应用代码几乎干净）
- **Mypy**: ⚠️ 1 error, 无覆盖（duplicate module path 阻塞）
- **Pytest collection**: 768 tests, 0 error, 1 pytest config warning
- **npm audit**: 1 high (vite), 2 moderate (esbuild, @vitest/ui)

---

## 维度 1：代码质量

### P1

- **[CQ-P1-01] SSE 事件字符串 18+ 处重复** — `application/chat_stream_service.py:83-361` 等
- **[CQ-P1-02] Pydantic 响应模型重复定义** — `DeleteResponse` ×3、`ExhibitListResponse` ×2
- **[CQ-P1-03] 后端硬编码中文 UI 串 289 处** — 导致 i18n/测试/可替换性负担

### P2

- **[CQ-P2-01]** `document_service.py:232` 底部 import + `# noqa: E402` 绕过循环依赖
- **[CQ-P2-02]** `VisitorProfileRepository` 双定义（domain vs application）
- **[CQ-P2-03]** `curator_tools.py` 627 行，含 6+ BaseTool 子类 + TSP helpers
- **[CQ-P2-04]** `rerank.py` 454 行，3 个 provider 共享一个文件
- **[CQ-P2-05]** `postgres/models.py` 457 行，所有 ORM 模型在单文件

### P3（聚合）

- Ruff 36 errors：多为 E501/E402/B023/B007/F401，集中在 `tests/performance/` 与 migration 脚本
- 3 处宽泛 `except Exception:`：`api/documents.py:122,174`、`postgres/database.py:97`
- 整个代码库 **0 TODO/FIXME/HACK 标记**（异常优秀）

---

## 维度 2：架构

### 层违规映射

| 来源 | 违规目标 | 数量 | 说明 |
|---|---|---|---|
| domain/ | application/、infra/、api/ | **0** | 清洁 |
| application/ | api/ | 0 | 清洁 |
| infra/ | application/ | **6** | 全部在 `infra/langchain/*` |
| workflows/ | application/ | 3 | workflow 层职责不清 |
| workflows/ | infra/ | 1 | `multi_turn.py:4` |

### P1

- **[ARCH-P1-01] Infra 反向依赖 application（6 处）**
  - `infra/langchain/agents.py:15`, `curator_agent.py:17`, `__init__.py:10`, `curator_tools.py:19` → `application.prompt_gateway`
  - `infra/langchain/tools.py:11` → `application.context_manager`
  - `infra/langchain/retrievers.py:8` → `application.retrieval`
- **[ARCH-P1-02] 双重 Port 系统**
  - `domain/repositories.py`: `ExhibitRepository`, `TourPathRepository`, `VisitorProfileRepository`
  - `application/ports/repositories.py`: 9 个 `*Port` 协议，签名与上条有漂移
- **[ARCH-P1-03] `workflows/` 层位置未定义**，既引用 application 又引用 infra，包含模块级可变全局状态 `set_prompt_gateway`

### P2

- **[ARCH-P2-01]** Repository adapter 3 处放法不一（`adapters/` vs `repositories.py` 顶层 vs `prompt_repository.py`）
- **[ARCH-P2-02]** 贫血领域模型（`ChatSession.add_message` / `close` = `pass`）
- **[ARCH-P2-03]** `set_prompt_gateway` 模块级可变全局
- **[ARCH-P2-04]** `main.py` lifespan 内部延迟 import 规避循环

---

## 维度 3：测试

### 覆盖矩阵缺口（application 服务）

未被任何测试 import 的服务：
- `chat_stream_service` ← **核心流式 RAG**（P0）
- `chat_session_service`, `chat_message_service`
- `curator_service`（application 层，不是 infra agent）
- `exhibit_service`, `profile_service`
- `error_handling`（安全相邻）

API 路由缺 contract 测试：`profile.py`, `exhibits.py`（public）

### P0

- **[TEST-P0-01]** `chat_stream_service.py`（361 LOC）无任何单元测试；SSE 事件契约、error sanitization、guest vs authenticated 分支均无覆盖

### P1

- **[TEST-P1-01]** 6 个 application 服务零引用
- **[TEST-P1-02]** `profile.py` / `exhibits.py`（public）无 contract 测试
- **[TEST-P1-03]** `test_layer_import_rules.py` 用过窄白名单，漏掉了本次审计发现的 6 处违规
- **[TEST-P1-04]** `contract/conftest.py:7-40` 直接操作 `db_module._engine` 全局，混用 `asyncio.run` + `loop.create_task`

### P2

- **[TEST-P2-01]** `test_llm_provider.py` 52 个 mock、`test_rag_agent.py` 30 个、`test_curator_agent.py` 29 个 — 过度 mock
- **[TEST-P2-02]** Contract conftest 自动 mock 所有 singleton，掩盖了 DI 连线问题
- **[TEST-P2-03]** pytest `collect_ignore_glob` 配置项未知
- **[TEST-P2-04]** `performance/config.py` `TestConfig` dataclass 触发 pytest collection warning

---

## 维度 4：安全

### P1

- **[SEC-P1-01]** `vite` 8.0.3 含 HIGH 路径遍历 CVE（GHSA-4w7w-66w2-5vf9）
- **[SEC-P1-02]** `verify_token` 不校验 `type == "access"`（`jwt_handler.py:45-50`）
- **[SEC-P1-03]** 文档上传无 content-type / 扩展名 / magic-number 校验
- **[SEC-P1-04]** CSRF 防御仅依赖 `SameSite=lax`（cookie 与 Bearer 并存）

### P2

- **[SEC-P2-01]** `create_refresh_token` 存在但无 `/refresh` 端点（半成品 crypto）
- **[SEC-P2-02]** Admin 通过 `ADMIN_EMAILS` 白名单升级，无邮件验证
- **[SEC-P2-03]** bcrypt 72 字节截断无预 hash
- **[SEC-P2-04]** 无密码强度策略（min_length、breached-list）
- **[SEC-P2-05]** Prompt injection 无防御（检索上下文直拼入 LLM prompt）

### P3

- SSE 断连时仍可用已失效 token 续流（需核查每 chunk 是否检查黑名单）
- `ALLOW_INSECURE_DEV_DEFAULTS=false` 默认项已设（良好）
- 日志层缺集中化 PII scrubbing

---

## 维度 5：性能与运维

### P1

- **[PERFOPS-P1-01]** `exhibit_service.list_exhibits` 无 filter 时加载全表 + Python 切片
- **[PERFOPS-P1-02]** 15 处 `except Exception as e:`，`tour_chat_service.py:94` 异常后仍发 `done`
- **[PERFOPS-P1-03]** `trace_id`（chat）与 `request_id`（HTTP）无桥接

### P2

- **[PERFOPS-P2-01]** Alembic 索引创建无 CONCURRENTLY
- **[PERFOPS-P2-02]** DB pool size 5 + overflow 10 偏紧（SSE 场景）
- **[PERFOPS-P2-03]** Tour event record fire-and-forget，只 warning
- **[PERFOPS-P2-04]** 启动时 ES/Redis 不可用即 fast-fail，无退化模式
- **[PERFOPS-P2-05]** Admin list 端点无 MAX_LIMIT 上限

### P3

- SSE 无 keepalive
- Embedding cache key 稳定性（含 model 版本否？）
- `get_session_maker` 重复 engine 创建路径
- Loguru 使用 f-string 多、`extra={}` 少（结构化日志不一致）

### 迁移安全速览

5 个迁移全部有 `downgrade()`；全部为 schema-only（无数据迁移混入）；全部使用阻塞式 `create_index`。对于当前规模合适；未来大表需要改 CONCURRENTLY。

---

## 维度 6：文档与依赖

### P1

- **[DOC-P1-01]** CLAUDE.md router 列表缺 6 个（admin/、client_ip、curator、exhibits、profile、tour）
- **[DOC-P1-02]** CLAUDE.md env vars 列 13 个，实际 30+（缺 `ADMIN_EMAILS`、`TRUSTED_PROXIES`、`RERANK_*`、`LOG_*`、`CORS_*`、`RATE_LIMIT_ENABLED`、`ALLOW_INSECURE_DEV_DEFAULTS`、`EMBEDDING_DIMS` 等）
- **[DOC-P1-03]** 50+ 端点均无 `summary=` 参数
- **[DOC-P1-04]** vite 高危 CVE + vitest/jsdom/vue-router 均有 major upgrade path

### P2

- **[DOC-P2-01]** `elasticsearch<9.0`、`langchain-community<0.4.0` 上限无注释原因
- **[DOC-P2-02]** 遗留顶层 debt 文档（`TECHNICAL_DEBT_AUDIT_2026-04-06.md`）与 `docs/audit/` 新目录并存
- **[DOC-P2-03]** `docs/plans/` 20+ 份计划无 status 标记

### P3

- 无 `docs/adr/` 目录 — 关键设计决策（RRF、LangGraph、workflows/、admin whitelist 等）仅在 git 中
- README 特性列表未跟上 tour / curator / prompt management
- `frontend/package.json` license "ISC" 默认值

---

## 跨维度系统性债务

下列问题跨越多个维度，单独修复成本高但合并修复性价比高：

### SYS-1: `infra/langchain/` 是分层债务的震中
- 架构 [ARCH-P1-01]：6 处反向依赖
- 代码质量 [CQ-P2-03]：`curator_tools.py` 627 行
- 测试 [TEST-P2-01]：52 mock 的 `test_llm_provider.py`
- 架构测试 [TEST-P1-03]：layer-rules 白名单漏掉 agents/curator_agent 以外的违规
- **合并收益**：一次针对 langchain 子系统的重构 + port 化可以同时还清 4 项债务

### SYS-2: 双 Port 系统 + 双中文策略 = 架构决策未写
- 架构 [ARCH-P1-02]：Port 系统双定义
- 文档 [P3]：无 ADR 记录为何存在两套
- 测试：两套 port 各自有实现，契约测试无法统一
- **合并收益**：一次决策 ADR + port 统一 + 目录整合，同时还清 3 项

### SYS-3: SSE 事件契约分散在 18 个字符串字面量中
- 代码质量 [CQ-P1-01]
- 测试 [TEST-P0-01]：因为契约分散，测试难以覆盖
- 运维 [PERFOPS-P1-02]：`tour_chat_service` error+done 矛盾是契约没有单一真相的后果
- 前端对接：事件类型在前端 `useChat.js` / `useTour.js` 手写 switch
- **合并收益**：定义 `sse_events.py` + 单元测试 + 前端 TS 类型导出，三层共用契约

### SYS-4: 类型检查 + 层规则检查都"通过"但实际无效
- 测试 [TEST-P1-03]：layer-rules 白名单过窄
- 运维：mypy 因 duplicate module 路径完全未跑
- CI 错觉：绿灯但零价值
- **合并收益**：修复 mypy 根因 + 重写 layer test = CI 从"表演"变成"防线"

### SYS-5: 文档漂移集中在 tour/curator/admin 这几个快速迭代区域
- 文档 [DOC-P1-01, DOC-P1-02]
- 架构：新加的 workflows/、curator、tour 未在 CLAUDE.md 和 README 被纳入
- 每次加 feature 忘更 CLAUDE.md → Claude agent 上下文错 → 下次改动基于错误模型
- **合并收益**：一次 CLAUDE.md + README 全面同步 + 建立 "改 API 即改 doc" 的 PR checklist

---

## Top 10 优先修复清单（推荐整改顺序）

| # | ID | 维度 | 描述 | 估工 | 理由 |
|---|---|---|---|---|---|
| 1 | SEC-P1-01 | 安全 | 升级 vite >=8.0.8 + 规划 vitest 4.x | 0.5d | CVE，修复成本极低 |
| 2 | TEST-P1-03 + mypy | 测试/运维 | 修 mypy 重复模块错误 + 重写 layer rules test（严格化） | 1d | CI 从无效到有效；所有后续修复都依赖此防线 |
| 3 | ARCH-P1-01 + ARCH-P1-02 + SYS-2 | 架构 | 统一 Port 到 `application/ports/`；移动 `prompt_gateway`/`context_manager`/`rrf_fusion` 让 infra/langchain 不再反向依赖 | 3-5d | 核心系统性债务；一次还清 6 处违规 + 2 套 Port |
| 4 | TEST-P0-01 + SYS-3 | 测试/代码 | 抽取 `sse_events.py`，为 chat_stream_service 补单元测试 | 2d | 核心业务逻辑从 0 测试 → 契约测试 |
| 5 | SEC-P1-02 + SEC-P2-01 | 安全 | `verify_token` 校验 type；决定 refresh 是"完成"还是"删除" | 0.5d | 低成本正确性修复 |
| 6 | SEC-P1-03 | 安全 | 文档上传加 content-type/扩展名/magic-number 校验 | 1d | 减少攻击面 |
| 7 | PERFOPS-P1-01 | 性能 | `list_all` 类方法下放 SKIP/LIMIT 到 SQL | 1d | 修复扩展性 cliff |
| 8 | TEST-P1-01 | 测试 | 为 6 个零覆盖 service 补单元测试 | 3d | 可靠性 |
| 9 | DOC-P1-01 + DOC-P1-02 + SYS-5 | 文档 | CLAUDE.md 全面同步（router/table/env/架构图） | 1d | 防止后续 agent 上下文错 |
| 10 | DOC-P1-03 | 文档 | 给 50+ 端点加 `summary=` + 启用 lint 规则 | 1d | 一次性投入，长期受益 |

**总估工约 14-16 人日**。如按并行路径分 2 人，可在 2 周内闭合 P0/P1 主干；P2/P3 作为后续"清洁日"处理。

---

## 附录 A：验证命令原始输出（节选）

### Ruff（36 errors）
```
backend/alembic/versions/002_add_created_at_indexes.py:10: F401 sqlalchemy imported but unused
backend/alembic/versions/20260415_add_tour_tables.py:162: E501 Line too long (143 > 120)
backend/scripts/migrate_prompts.py: E501 (5 occurrences)
backend/tests/architecture/test_no_main_runtime_imports.py:58: B023
backend/tests/architecture/test_no_main_runtime_imports.py:102: E501
backend/tests/e2e/conftest.py:44: E501
backend/tests/integration/test_rate_limit_integration.py:254: E501
backend/tests/performance/*: 15× E402 module level import not at top
backend/tests/performance/start_mock_services.py:104: B007
backend/tests/unit/test_parallel_indexing.py:325,331: B023
```

### Mypy
```
backend/app/infra/postgres/models.py: error: Source file found twice under different module names:
  "app.infra.postgres.models" and "backend.app.infra.postgres.models"
Found 1 error in 1 file (errors prevented further checking)
```
（典型根因：mypy 同时扫描 `backend/app/` 和 `backend/` 根；修法：把 `backend/app/` 作为 mypy 的根，或在 `[tool.mypy]` 设 `explicit_package_bases=true` + `mypy_path`。）

### Pytest collection
```
768 tests collected in 1.66s
PytestConfigWarning: Unknown config option: collect_ignore_glob
PytestCollectionWarning: cannot collect test class 'TestConfig' (performance/config.py)
```

### npm audit
```
vite: HIGH, GHSA-4w7w-66w2-5vf9 (CWE-22 Path Traversal), range <=6.4.1 / 8.0.0-8.0.4
esbuild: MODERATE, GHSA-67mh-4wv8-2f99 (CWE-346)
@vitest/ui: MODERATE (transitive via vitest)
```

### uv pip list --outdated（节选关键）
```
elasticsearch     8.19.3 → 9.3.0   (major; pyproject caps <9.0.0)
fastapi           0.135.3 → 0.136.0
pydantic          2.12.5 → 2.13.1
pydantic-core     2.41.5 → 2.46.1
langchain-community 0.3.31 → 0.4.1  (major; pyproject caps <0.4.0)
openai            2.30.0 → 2.32.0
uvicorn           0.43.0 → 0.44.0
```

## 附录 B：扫描方法说明

本次审计原计划通过 6 个并行 subagent 分维度扫描（代码质量 / 架构 / 测试 / 安全 / 性能运维 / 文档依赖），但全部 6 个 agent 均因上游 API 网关 `new-api` panic（`nil pointer dereference`）在 ~165-180 秒同步失败。

pivot 为**主线程顺序扫描**：逐维度使用 `Read`/`Grep`/`Glob`/`Bash` 工具静态分析 + 结合 `ruff` / `mypy` / `pytest --collect-only` / `npm audit` / `uv pip list --outdated` 动态验证命令。该方法耗时更长但结果直接可控。

扫描覆盖：
- 86 个 backend Python 文件（12,870 LOC）
- 62 个 frontend Vue/TS 文件（6,969 LOC）
- 5 个 Alembic 迁移脚本
- 83 个测试文件（768 测试用例）
- `CLAUDE.md`, `README.md`, `pyproject.toml`, `frontend/package.json`, `.env.example`, 30 份 `docs/`
