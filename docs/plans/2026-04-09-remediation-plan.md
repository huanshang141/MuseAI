# MuseAI 技术债务修复计划

**版本**: v1.0
**制定日期**: 2026-04-09
**基准审计**: [2026-04-09 技术债务审计报告](2026-04-09-technical-debt-audit.md)
**计划周期**: 2026-04-10 ~ 2026-06-10（8周）
**状态**: 待审批

---

## 目录

- [一、计划总览](#一计划总览)
- [二、阶段规划与里程碑](#二阶段规划与里程碑)
- [三、任务详细定义](#三任务详细定义)
  - [Phase 1: P0 紧急修复](#phase-1-p0-紧急修复)
  - [Phase 2: P1 短期修复](#phase-2-p1-短期修复)
  - [Phase 3: P2 中期改进](#phase-3-p2-中期改进)
  - [Phase 4: P3 长期优化](#phase-4-p3-长期优化)
- [四、任务依赖关系图](#四任务依赖关系图)
- [五、风险管理](#五风险管理)
- [六、验收总则](#六验收总则)

---

## 一、计划总览

### 总体目标

基于 2026-04-09 审计发现的 57 项技术债务，制定分阶段、可追踪、可验收的修复计划，确保系统安全性、架构合理性和运行性能达到生产级标准。

### 任务统计

| 阶段 | 优先级 | 任务数 | 涉及审计项 | 预计工时 | 时间窗口 |
|------|--------|--------|-----------|---------|---------|
| Phase 1 | P0 | 6 | 6项 Critical | 40h | 第1-3天 |
| Phase 2 | P1 | 10 | 11项 High | 120h | 第1-2周 |
| Phase 3 | P2 | 12 | 12项 Medium | 100h | 第3-4周 |
| Phase 4 | P3 | 10 | 10项 Low | 80h | 第5-8周 |
| **合计** | — | **38** | **39项** | **340h** | **8周** |

> 注：部分审计项已合并为同一任务（如 SEC-C2+SEC-C3 合并为环境配置安全加固），部分 Low 级别项延后至持续改进阶段。

---

## 二、阶段规划与里程碑

| 里程碑 | 日期 | 交付物 | 验收标准 |
|--------|------|--------|---------|
| M1: P0 完成 | 第3天 | 安全紧急修复合入 main | 0 个 Critical 安全问题；所有 P0 任务验收通过 |
| M2: P1 完成 | 第2周末 | 架构修复+安全加固合入 main | 0 个 High 安全问题；单元测试全绿；架构测试覆盖5个服务 |
| M3: P2 完成 | 第4周末 | 性能优化+代码质量提升合入 main | MyPy 错误 < 20；Ruff 错误 = 0；速率限制原子化 |
| M4: P3 完成 | 第8周末 | 长期优化项合入 main | 前端虚拟滚动上线；Token 刷新机制可用；构建产物优化 |

---

## 三、任务详细定义

---

### Phase 1: P0 紧急修复

---

#### TASK-001: API 异常详情泄露修复

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-C1 |
| **所属模块** | backend/app/api |
| **严重程度** | Critical |
| **风险评分** | 25 (影响5 × 可能性5) |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

curator.py 和 profile.py 中的异常处理直接将 `str(e)` 作为 HTTP 响应的 `detail` 返回给客户端，可能泄露内部路径、数据库结构、堆栈信息等敏感数据。而同项目的 document_service 和 chat_service 已实现错误消息消毒（`sanitize_error_message`），存在处理不一致。

**受影响代码**

- `backend/app/api/curator.py:158` — `HTTPException(status_code=500, detail=str(e))`
- `backend/app/api/curator.py:187` — `HTTPException(status_code=500, detail=str(e))`
- `backend/app/api/profile.py:89` — `HTTPException(status_code=500, detail=str(e))`

**修复实施步骤**

1. 在 `backend/app/application/` 下创建通用错误消毒模块，或复用 `document_service.sanitize_error_message`
2. 将 `curator.py:158` 的 `detail=str(e)` 替换为 `detail=sanitize_error_message(e)`
3. 将 `curator.py:187` 的 `detail=str(e)` 替换为 `detail=sanitize_error_message(e)`
4. 将 `profile.py:89` 的 `detail=str(e)` 替换为 `detail=sanitize_error_message(e)`
5. 确保原始异常信息仍通过 `logger.error()` 记录到服务端日志

**验收标准**

- [ ] 三个端点在异常时返回通用错误消息，不包含任何内部实现细节
- [ ] 服务端日志仍记录完整异常信息（含 traceback）
- [ ] `uv run pytest backend/tests/contract/ -v` 全部通过
- [ ] 手动测试：触发 curator/profile 异常，响应体不包含文件路径、SQL 语句等

---

#### TASK-002: 环境配置安全加固

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-C2, SEC-C3 |
| **所属模块** | 项目根目录 / 配置 |
| **严重程度** | Critical |
| **风险评分** | 20 (SEC-C3), 16 (SEC-C2) |
| **预计工时** | 3h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. `.env.example` 第6行包含硬编码数据库密码 `museai123`，开发者可能直接复制使用
2. `.env.example` 第4行 `ALLOW_INSECURE_DEV_DEFAULTS=true`，新部署默认启用不安全模式，JWT 密钥和 API 密钥可能使用开发默认值
3. `alembic.ini` 同样包含硬编码数据库密码

**受影响代码**

- `.env.example:4` — `ALLOW_INSECURE_DEV_DEFAULTS=true`
- `.env.example:6` — `DATABASE_URL=postgresql+asyncpg://museai:museai123@localhost:5432/museai`
- `alembic.ini` — `sqlalchemy.url = postgresql+psycopg2://museai:museai123@localhost:5432/museai`

**修复实施步骤**

1. 修改 `.env.example` 第4行：`ALLOW_INSECURE_DEV_DEFAULTS=false`
2. 修改 `.env.example` 第6行：将 `museai123` 替换为 `CHANGE_ME_STRONG_PASSWORD`
3. 修改 `alembic.ini`：将硬编码 URL 替换为从环境变量读取的方式（使用 `%(DATABASE_URL)s` 或在 `env.py` 中从 `os.environ` 获取）
4. 在 `.env.example` 中添加注释说明每个敏感配置项的安全要求
5. 验证 `ALLOW_INSECURE_DEV_DEFAULTS=false` 时，未配置密钥的应用启动会报错而非静默使用默认值

**验收标准**

- [ ] `.env.example` 中无任何硬编码密码或密钥
- [ ] `ALLOW_INSECURE_DEV_DEFAULTS` 默认值为 `false`
- [ ] `alembic.ini` 不包含硬编码密码
- [ ] 不修改 `.env.example` 直接启动应用时，生产模式报错提示配置缺失
- [ ] 开发环境设置 `ALLOW_INSECURE_DEV_DEFAULTS=true` 后可正常启动

---

#### TASK-003: 文件上传流式处理改造

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-C1 |
| **所属模块** | backend/app/api/documents.py |
| **严重程度** | Critical |
| **风险评分** | 15 (影响5 × 可能性3) |
| **预计工时** | 8h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`documents.py:171` 使用 `await file.read()` 将整个上传文件（最大 50MB）一次性读入内存，高并发上传时可能导致 OOM。文件内容解码后又在内存中保留一份字符串副本，后台任务处理时还存在多份拷贝。

**受影响代码**

- `backend/app/api/documents.py:115` — `MAX_FILE_SIZE = 50 * 1024 * 1024`
- `backend/app/api/documents.py:171` — `content = await file.read()`
- `backend/app/api/documents.py:172` — `text_content = content.decode("utf-8")`

**修复实施步骤**

1. 实现流式文件读取函数：使用 `async for chunk in file.chunks()` 分块读取，累计大小校验不超过 50MB
2. 将文件内容写入临时文件（`tempfile.NamedTemporaryFile`），而非全部保留在内存
3. 修改文档处理逻辑：从临时文件路径读取内容进行分块和索引
4. 在后台任务处理完成后清理临时文件
5. 添加文件上传内存使用监控指标

**技术选型**

- 临时文件管理：Python 标准库 `tempfile` + `aiofiles` 异步文件写入
- 流式读取：FastAPI `UploadFile.chunks()` 方法（默认 64KB 分块）
- 资源清理：使用 `try/finally` 确保临时文件删除

**验收标准**

- [ ] 上传 50MB 文件时，进程内存增长不超过 10MB（对比修复前可能增长 100MB+）
- [ ] 并发 10 个 10MB 文件上传，进程内存不超过 500MB
- [ ] 文件上传功能正常：上传 → 分块 → 索引 → 搜索 全流程通过
- [ ] `uv run pytest backend/tests/contract/test_documents_api.py -v` 全部通过
- [ ] 临时文件在处理完成（无论成功或失败）后被正确清理

---

#### TASK-004: Embedding Provider 重试机制

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-C2 |
| **所属模块** | backend/app/infra/providers/embedding.py |
| **严重程度** | Critical |
| **风险评分** | 12 (影响4 × 可能性3) |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`OllamaEmbeddingProvider` 的 `embed_text` 方法没有任何重试逻辑，Ollama 服务超时或临时不可用时整个文档摄取流程直接失败。而同项目的 LLM Provider 和 Rerank Provider 均已实现3次指数退避重试。

**受影响代码**

- `backend/app/infra/providers/embedding.py:41-57` — `embed_text` 无重试
- `backend/app/infra/providers/embedding.py:59-66` — `embed_batch` 无重试

**修复实施步骤**

1. 参照 `backend/app/infra/providers/rerank.py:70-87` 的重试模式，提取通用重试装饰器或工具函数
2. 为 `embed_text` 添加重试逻辑：3次重试，指数退避（1s, 2s, 4s），仅对 `httpx.TimeoutException` 和 `httpx.HTTPStatusError(5xx)` 重试
3. 为 `embed_batch` 添加同样的重试逻辑
4. 添加重试次数和延迟的配置参数（`max_retries`, `retry_delay`），与 LLM/Rerank Provider 保持一致
5. 添加重试日志记录（WARNING 级别）

**验收标准**

- [ ] Ollama 服务超时时自动重试最多3次
- [ ] 4xx 错误不重试，5xx 和超时错误重试
- [ ] 重试日志记录包含重试次数和延迟时间
- [ ] `uv run pytest backend/tests/unit/test_embedding_provider.py -v` 全部通过
- [ ] 新增重试行为的单元测试（mock 超时场景）

---

#### TASK-005: Redis 故障 fail-open 日志告警

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-H1 |
| **所属模块** | backend/app/api/deps.py |
| **严重程度** | High |
| **风险评分** | 12 (影响3 × 可能性4) |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`get_current_user` 中 Redis 故障时 fail-open（跳过 token 黑名单检查），但没有任何日志记录。`get_optional_user` 中 Redis 异常更是静默 `pass`。这使得运维人员无法感知 Redis 故障对安全性的影响。

**受影响代码**

- `backend/app/api/deps.py:104-114` — `get_current_user` 中 Redis 故障无日志
- `backend/app/api/deps.py:164-166` — `get_optional_user` 中 Redis 异常静默忽略

**修复实施步骤**

1. 在 `get_current_user` 的 Redis 异常处理中添加 `logger.warning(f"Redis error during blacklist check, fail-open: {e}")`
2. 在 `get_optional_user` 的 Redis 异常处理中添加 `logger.warning(f"Redis error during optional user blacklist check: {e}")`
3. 考虑添加结构化指标（如 `redis_fail_open_total` 计数器），便于监控告警

**验收标准**

- [ ] Redis 故障时日志输出 WARNING 级别告警
- [ ] 日志包含足够信息用于排查（错误类型、影响范围）
- [ ] `uv run pytest backend/tests/unit/test_api_deps.py -v` 相关测试通过
- [ ] 不改变现有的 fail-open 行为（仅添加日志，不改变逻辑）

---

#### TASK-006: 非生产环境速率限制策略调整

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-H4, CODE-1, CODE-4 |
| **所属模块** | backend/app/api/deps.py, backend/tests/ |
| **严重程度** | High |
| **风险评分** | 12 (影响4 × 可能性3) |
| **预计工时**** | 8h |
| **前置依赖** | TASK-005 |
| **负责人** | 待分配 |

**问题描述**

1. `check_rate_limit`、`check_auth_rate_limit`、`check_guest_rate_limit` 在 `APP_ENV != "production"` 时直接 `return`，完全跳过速率限制
2. 导致7个单元测试失败（mock 场景下 `APP_ENV` 为 development，限流被跳过）
3. 导致2个契约测试失败（测试期望 429 但限流被跳过返回 200）

**受影响代码**

- `backend/app/api/deps.py:236-238` — `check_rate_limit` 非生产跳过
- `backend/app/api/deps.py:266-269` — `check_auth_rate_limit` 非生产跳过
- `backend/app/api/deps.py:310-312` — `check_guest_rate_limit` 非生产跳过
- `backend/tests/unit/test_api_deps.py` — 7个失败测试
- `backend/tests/unit/test_deps_security.py` — 2个失败测试
- `backend/tests/contract/test_chat_api.py:316` — 1个失败测试
- `backend/tests/contract/test_documents_api.py` — 1个失败测试

**修复实施步骤**

1. 引入 `RATE_LIMIT_ENABLED` 配置项（默认 `true`），替代基于 `APP_ENV` 的硬编码判断
2. 在 `settings.py` 中添加 `RATE_LIMIT_ENABLED: bool = True`
3. 修改三个限流函数：将 `if settings.APP_ENV != "production": return` 改为 `if not settings.RATE_LIMIT_ENABLED: return`
4. 在 `.env.example` 中添加 `RATE_LIMIT_ENABLED=true`
5. 更新 `test_api_deps.py` 中的 mock：为 `mock_request` 添加 `extract_client_ip` 所需的属性（`headers` 返回支持 `get()` 方法的对象）
6. 更新 `test_deps_security.py` 中的 mock：同上
7. 修复契约测试：在测试固件中设置 `RATE_LIMIT_ENABLED=true` 或使用 `APP_ENV=production`

**验收标准**

- [ ] `uv run pytest backend/tests/unit/test_api_deps.py -v` 全部通过
- [ ] `uv run pytest backend/tests/unit/test_deps_security.py -v` 全部通过
- [ ] `uv run pytest backend/tests/contract/test_chat_api.py -v` 全部通过
- [ ] `uv run pytest backend/tests/contract/test_documents_api.py -v` 全部通过
- [ ] 开发环境可通过 `RATE_LIMIT_ENABLED=false` 禁用限流（如压力测试需要）
- [ ] 生产环境默认启用限流，无需额外配置

---

### Phase 2: P1 短期修复

---

#### TASK-007: CORS 安全加固与配置验证

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-H2, SEC-H3, SEC-M2 |
| **所属模块** | backend/app/config, backend/app/main.py |
| **严重程度** | High |
| **风险评分** | 16 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. `CORS_ORIGINS` 默认值为 `"*"`，允许任何来源访问
2. `RERANK_API_KEY` 无生产环境验证，可能为空
3. `allow_methods` 和 `allow_headers` 均为 `["*"]`，未做方法限制

**修复实施步骤**

1. 修改 `settings.py:48`：`CORS_ORIGINS: str = "http://localhost:3000"`
2. 在 `settings.py` 的生产环境验证中添加 `RERANK_API_KEY` 必填检查（当 `RERANK_PROVIDER` 不为空时）
3. 修改 `main.py:245-246`：将 `allow_methods=["*"]` 改为 `allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]`，将 `allow_headers=["*"]` 改为 `allow_headers=["Authorization", "Content-Type"]`
4. 更新 `.env.example` 中的 CORS 配置说明

**验收标准**

- [ ] 默认 CORS 仅允许 `http://localhost:3000`
- [ ] 生产环境未配置 `RERANK_API_KEY` 时启动报错
- [ ] CORS 仅允许必要的 HTTP 方法和头部
- [ ] `uv run pytest backend/tests/unit/test_config.py -v` 通过
- [ ] 前端开发服务器可正常跨域访问 API

---

#### TASK-008: 六角架构修复 — 端口定义与依赖注入

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-C1 |
| **所属模块** | backend/app/application, backend/app/domain |
| **严重程度** | Critical |
| **风险评分** | 16 |
| **预计工时** | 16h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

5个应用服务直接导入基础设施层具体实现，违反六角架构的依赖规则。`auth_service` 更是通过函数内导入规避架构测试。缺失的端口定义导致应用层与基础设施层紧耦合。

**受影响代码**

| 服务 | 违规导入 |
|------|---------|
| chat_service | `app.infra.postgres.models`, `app.infra.providers.llm`, `app.infra.redis.cache` |
| exhibit_service | `app.infra.postgres.repositories.PostgresExhibitRepository` |
| profile_service | `app.infra.postgres.repositories.PostgresVisitorProfileRepository` |
| curator_service | `app.infra.langchain.curator_agent.CuratorAgent` |
| auth_service | `app.infra.postgres.models.User`（函数内导入） |

**修复实施步骤**

1. **定义缺失端口**（`backend/app/application/ports/repositories.py`）：
   - `ExhibitRepositoryPort`（Protocol）
   - `VisitorProfileRepositoryPort`（Protocol）
   - `ChatSessionRepositoryPort`（Protocol）
   - `ChatMessageRepositoryPort`（Protocol）
   - `LLMProviderPort`（Protocol）
   - `CachePort`（Protocol）
   - `CuratorAgentPort`（Protocol）

2. **重构 exhibit_service**：
   - 构造函数接收 `ExhibitRepositoryPort`
   - 移除 `from app.infra.postgres.repositories import PostgresExhibitRepository`
   - 在 `main.py` lifespan 中注入 `PostgresExhibitRepository` 实例

3. **重构 profile_service**：
   - 构造函数接收 `VisitorProfileRepositoryPort`
   - 移除 `from app.infra.postgres.repositories import PostgresVisitorProfileRepository`
   - 在 `main.py` lifespan 中注入实例

4. **重构 curator_service**：
   - 构造函数接收 `CuratorAgentPort`
   - 移除 `from app.infra.langchain.curator_agent import CuratorAgent`
   - 在 `main.py` lifespan 中注入实例

5. **重构 auth_service**：
   - 将函数内 `from app.infra.postgres.models import User` 提升为端口依赖
   - 定义 `UserRepositoryPort` 的 `get_by_email` 方法返回领域实体而非 ORM 模型

6. **重构 chat_service**（最复杂，可与 TASK-009 协同）：
   - 构造函数接收 `ChatSessionRepositoryPort`, `ChatMessageRepositoryPort`, `LLMProviderPort`, `CachePort`
   - 移除所有 `app.infra.*` 直接导入

7. **更新 main.py lifespan**：在初始化阶段组装所有依赖并注入到应用服务

**验收标准**

- [ ] `application/` 目录下无任何 `from app.infra` 导入（模块级和函数级）
- [ ] 所有应用服务通过构造函数接收端口依赖
- [ ] `uv run pytest backend/tests/architecture/ -v` 全部通过
- [ ] 新增架构测试覆盖 chat_service、exhibit_service、profile_service、curator_service
- [ ] `uv run pytest backend/tests/ -q --ignore=backend/tests/performance -k "not e2e"` 失败数 ≤ 3

---

#### TASK-009: chat_service 拆分重构

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-H1, PERF-H1 |
| **所属模块** | backend/app/application/chat_service.py |
| **严重程度** | High |
| **风险评分** | 12 |
| **预计工时** | 12h |
| **前置依赖** | TASK-008 |
| **负责人** | 待分配 |

**问题描述**

`chat_service.py` 包含 534 行代码，承担了会话 CRUD、消息 CRUD、RAG 问答、流式响应生成、SSE 事件格式化、错误消息清理、持久化管理等7项职责，严重违反单一职责原则。同时流式传输中使用 `+=` 拼接字符串，长回答时产生大量临时对象。

**修复实施步骤**

1. **拆分为3个服务**：
   - `ChatSessionService`：会话 CRUD（create_session, get_sessions_by_user, get_session_by_id, delete_session）
   - `ChatMessageService`：消息 CRUD（get_messages_by_session, save_message）
   - `ChatStreamService`：RAG 问答 + 流式响应（ask_question_stream_with_rag, 事件格式化）

2. **修复字符串拼接**（PERF-H1）：
   - 将 `full_content += chunk` 替换为 `chunks_list.append(chunk)` + `"".join(chunks_list)`
   - 同样修复 `chat_service.py:339-340` 的拼接

3. **更新 API 路由**（`chat.py`）：注入拆分后的服务

4. **更新测试**：将现有 `test_chat_service*.py` 拆分对应到新服务

**验收标准**

- [ ] 每个服务文件不超过 200 行
- [ ] 每个服务仅包含单一职责相关方法
- [ ] `uv run pytest backend/tests/unit/test_chat_service*.py -v` 全部通过
- [ ] `uv run pytest backend/tests/contract/test_chat_api.py -v` 全部通过
- [ ] 流式传输功能正常，SSE 事件格式不变
- [ ] 字符串拼接已替换为 `list.append` + `join`

---

#### TASK-010: 统一单例获取机制

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-H2 |
| **所属模块** | backend/app/main.py, backend/app/api/deps.py |
| **严重程度** | High |
| **风险评分** | 9 |
| **预计工时** | 6h |
| **前置依赖** | TASK-008 |
| **负责人** | 待分配 |

**问题描述**

`main.py:150-231` 定义了 12 个 `get_xxx()` 全局获取函数，直接引用模块级 `app` 变量；`deps.py` 通过 `Request.app.state` 获取同样的单例。两套机制并存，增加维护成本和出错概率。

**修复实施步骤**

1. 确认 `main.py` 中 `get_xxx()` 函数的所有调用方
2. 将调用方迁移到使用 `deps.py` 中的 `Depends(get_xxx_dep)` 方式
3. 移除 `main.py:150-231` 中的全局 getter 函数
4. 保留 `app.state` 作为单例存储位置（lifespan 中初始化），仅通过 `deps.py` 的 Depends 获取

**验收标准**

- [ ] `main.py` 中无 `get_xxx()` 全局获取函数
- [ ] 所有单例通过 `deps.py` 的 `Depends()` 获取
- [ ] `uv run pytest backend/tests/ -q --ignore=backend/tests/performance -k "not e2e"` 失败数 ≤ 3
- [ ] 应用启动和请求处理正常

---

#### TASK-011: 架构测试扩展

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-H3 |
| **所属模块** | backend/tests/architecture/ |
| **严重程度** | High |
| **风险评分** | 9 |
| **预计工时** | 4h |
| **前置依赖** | TASK-008 |
| **负责人** | 待分配 |

**问题描述**

现有架构测试仅检查 `auth_service` 和 `document_service` 的模块级导入，5个违规服务未被检测。`auth_service` 通过函数内导入规避了检测。

**修复实施步骤**

1. 在 `test_layer_import_rules.py` 中添加测试：
   - `test_chat_service_does_not_import_infra_modules`
   - `test_exhibit_service_does_not_import_infra_modules`
   - `test_profile_service_does_not_import_infra_modules`
   - `test_curator_service_does_not_import_infra_modules`
2. 增强检测逻辑：不仅检查模块级导入，还检查函数内导入（`ast` 解析或 `inspect.getsource` 分析）
3. 添加 API 层导入约束测试：`test_api_layer_does_not_import_infra_directly`

**验收标准**

- [ ] 新增5个架构测试全部通过
- [ ] 函数内导入也能被检测到
- [ ] 尝试在应用服务中添加 `from app.infra` 导入时，CI 构建失败
- [ ] `uv run pytest backend/tests/architecture/ -v` 全部通过

---

#### TASK-012: 数据库连接池优化

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-H2, PERF-M1, CODE-9 |
| **所属模块** | backend/app/infra/postgres/database.py, backend/app/infra/redis/cache.py |
| **严重程度** | High |
| **风险评分** | 9 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. PostgreSQL 连接池缺少 `pool_pre_ping=True`，可能使用已断开的连接
2. Redis 客户端使用默认连接池配置，高并发时连接可能不够
3. 测试环境数据库连接池缺少 `pool_timeout` 和 `pool_recycle` 配置

**修复实施步骤**

1. 在 `database.py:30` 的 `engine_kwargs` 中添加 `"pool_pre_ping": True`
2. 在 `database.py:69-74` 的测试路径中补充 `"pool_timeout": 30, "pool_recycle": 1800`
3. 在 `cache.py:8` 的 `Redis.from_url()` 中添加连接池配置：`connection_pool=ConnectionPool(max_connections=50)`
4. 在 `settings.py` 中添加 `REDIS_MAX_CONNECTIONS: int = 50` 配置项

**验收标准**

- [ ] PostgreSQL 连接池启用 `pool_pre_ping`
- [ ] Redis 连接池配置 `max_connections`
- [ ] 测试环境连接池配置与生产环境一致
- [ ] `uv run pytest backend/tests/unit/test_database_singleton.py -v` 通过
- [ ] 数据库连接断开后自动重连（模拟测试）

---

#### TASK-013: SSE 心跳与流式重试

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-H3, PERF-M5 |
| **所属模块** | backend/app/api/chat.py, backend/app/infra/providers/llm.py |
| **严重程度** | High |
| **风险评分** | 9 |
| **预计工时** | 6h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. SSE 流式响应无心跳机制，长时间无数据时代理/负载均衡器可能超时断开
2. LLM 流式调用无重试，生成中断无法恢复

**修复实施步骤**

1. 在 `chat.py` 的 `event_generator` 中添加心跳：每 30 秒发送 `:keepalive\n\n` SSE 注释
2. 使用 `asyncio.wait_for` + 超时机制实现心跳定时器
3. 在 `llm.py` 的 `generate_stream` 方法中添加重试逻辑：
   - 捕获 `httpx.TimeoutException` 和连接错误
   - 最多重试2次（流式重试不宜过多）
   - 重试时从头开始新的流式请求
4. 在前端 `api/index.js` 中添加 SSE 超时处理：60秒无数据则重连

**验收标准**

- [ ] SSE 流在无数据时每 30 秒发送心跳
- [ ] LLM 流式调用超时后自动重试
- [ ] 前端 SSE 超时后自动重连
- [ ] `uv run pytest backend/tests/unit/test_chat_service_streaming.py -v` 通过
- [ ] 压力测试中 SSE 连接不再被代理超时断开

---

#### TASK-014: 测试脚本安全修复

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-H6 |
| **所属模块** | scripts/ |
| **严重程度** | High |
| **风险评分** | 8 |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`scripts/init_exhibits.py:1373` 使用 `password_hash="test"` 作为用户密码哈希，若误用于生产环境，任何人可用简单密码登录。

**修复实施步骤**

1. 使用 `bcrypt.hashpw(b"changeme", bcrypt.gensalt()).decode()` 生成真实的 bcrypt 哈希
2. 替换 `password_hash="test"` 为生成的 bcrypt 哈希
3. 在脚本头部添加醒目注释：`# WARNING: This script is for DEVELOPMENT ONLY. Do NOT run in production.`
4. 添加 `--env` 参数检查：当 `APP_ENV=production` 时拒绝执行

**验收标准**

- [ ] 脚本使用 bcrypt 哈希而非明文
- [ ] 脚本在 `APP_ENV=production` 时拒绝执行
- [ ] 开发环境执行脚本后，用户可使用预期密码登录
- [ ] `uv run pytest backend/tests/unit/test_debt_marker_scan_script.py -v` 通过

---

#### TASK-015: Cookie 安全标志与 SameSite 策略

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-H5, SEC-M4 |
| **所属模块** | backend/app/api/auth.py |
| **严重程度** | High |
| **风险评分** | 6 |
| **预计工时** | 3h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. Cookie `secure` 标志仅在 `APP_ENV == "production"` 时启用
2. `SameSite` 设置为 `lax` 而非 `strict`

**修复实施步骤**

1. 修改 `auth.py:122`：将 `secure=settings.APP_ENV == "production"` 改为 `secure=True`
2. 添加 `settings.py` 配置项 `COOKIE_SECURE: bool = True`，允许开发环境显式关闭
3. 评估 `SameSite=strict` 的可行性：分析是否有从外部链接发起的 GET 请求需要携带 cookie 的场景
4. 如果无外部链接场景，将 `samesite="lax"` 改为 `samesite="strict"`
5. 更新开发环境文档：说明本地开发需配置 HTTPS（如使用 `mkcert`）

**验收标准**

- [ ] Cookie 在所有环境默认启用 `secure` 标志
- [ ] `SameSite` 策略评估完成并有文档记录
- [ ] 开发环境可通过配置关闭 `secure`（仅限本地开发）
- [ ] `uv run pytest backend/tests/contract/test_auth_api.py -v` 通过

---

#### TASK-016: CuratorAgent 异步重构

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-H4 |
| **所属模块** | backend/app/infra/langchain/curator_agent.py |
| **严重程度** | High |
| **风险评分** | 8 |
| **预计工时** | 6h |
| **前置依赖** | TASK-008 |
| **负责人** | 待分配 |

**问题描述**

`CuratorAgent.__init__` 中使用 `ThreadPoolExecutor` + `asyncio.run()` 在已有事件循环中执行异步代码，`future.result()` 阻塞当前线程，是反模式。

**修复实施步骤**

1. 将 `CuratorAgent` 的初始化改为异步工厂方法（`@classmethod async def create(cls, ...)`）
2. 移除 `ThreadPoolExecutor` 和 `asyncio.run()` 嵌套
3. 直接 `await` 异步操作获取 prompt
4. 更新 `main.py` lifespan 中的初始化代码：`await CuratorAgent.create(...)`
5. 更新 `curator_service` 的依赖注入方式

**验收标准**

- [ ] `CuratorAgent` 不再使用 `ThreadPoolExecutor` 和 `asyncio.run()`
- [ ] 初始化过程完全异步，无阻塞调用
- [ ] `uv run pytest backend/tests/unit/test_curator_agent.py -v` 通过
- [ ] 策展功能端到端测试通过

---

### Phase 3: P2 中期改进

---

#### TASK-017: 速率限制原子化

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-M1 |
| **所属模块** | backend/app/infra/redis/cache.py |
| **严重程度** | Medium |
| **风险评分** | 9 |
| **预计工时** | 6h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`check_rate_limit` 使用 `set nx` + `incr` 两步操作，高并发下存在竞态条件，可能导致超出限制。

**修复实施步骤**

1. 编写 Redis Lua 脚本，将 `set nx` + `incr` + TTL 检查合并为原子操作
2. 在 `RedisCache` 中添加 `_rate_limit_lua_script` 属性，使用 `self.client.register_script()`
3. 替换 `check_rate_limit` 方法实现为 Lua 脚本调用
4. 同步更新 `deps.py` 中 `check_auth_rate_limit` 和 `check_guest_rate_limit` 的直接 Redis 操作
5. 添加并发压力测试验证原子性

**验收标准**

- [ ] 速率限制操作为原子性（Lua 脚本）
- [ ] 并发 100 请求/秒时，速率限制计数准确
- [ ] `uv run pytest backend/tests/unit/test_redis_cache.py -v` 通过
- [ ] 新增并发速率限制测试通过

---

#### TASK-018: MyPy 类型标注修复

| 属性 | 值 |
|------|-----|
| **审计编号** | CODE-2 |
| **所属模块** | backend/app/ |
| **严重程度** | Medium |
| **风险评分** | 8 |
| **预计工时** | 8h |
| **前置依赖** | TASK-010 |
| **负责人** | 待分配 |

**问题描述**

MyPy 检查发现 146 个类型错误，集中在 `main.py`（13个，`app.state` 获取返回 Any）和 `admin/`（9个，`CurrentAdminUser` 缺少类型参数）。

**修复实施步骤**

1. 为 `app.state` 的属性定义类型化接口（使用 `TypedDict` 或自定义 `AppState` 类）
2. 修复 `main.py` 中 getter 函数的返回类型标注
3. 修复 `admin/` 中 `CurrentAdminUser` 的类型参数
4. 修复 `auth.py:136` 缺失的返回类型标注
5. 修复 `curator.py:105` 的 `Any` 返回类型
6. 逐步消除其他文件的类型错误

**验收标准**

- [ ] `uv run mypy backend/app/ --ignore-missing-imports` 错误数 < 20
- [ ] `main.py` 中无类型错误
- [ ] `admin/` 中无类型错误
- [ ] CI 中 MyPy 检查通过

---

#### TASK-019: Ruff 代码规范修复

| 属性 | 值 |
|------|-----|
| **审计编号** | CODE-3 |
| **所属模块** | 全项目 |
| **严重程度** | Medium |
| **风险评分** | 6 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

Ruff 检查发现 136 个代码规范错误，其中 102 个可自动修复（主要是 UP006: `List` → `list`）。

**修复实施步骤**

1. 执行 `uv run ruff check --fix backend/app/` 自动修复 102 个问题
2. 手动修复剩余 34 个不可自动修复的问题
3. 在 CI 中添加 Ruff 检查门禁

**验收标准**

- [ ] `uv run ruff check backend/app/` 输出 0 errors
- [ ] 所有自动修复通过代码审查
- [ ] CI 中 Ruff 检查通过

---

#### TASK-020: ORM-领域实体映射完善

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-M1 |
| **所属模块** | backend/app/infra/postgres/ |
| **严重程度** | Medium |
| **风险评分** | 6 |
| **预计工时** | 8h |
| **前置依赖** | TASK-008 |
| **负责人** | 待分配 |

**问题描述**

仅 Exhibit 和 VisitorProfile 有完整的 ORM → 领域实体转换，User、ChatSession、ChatMessage、Document 等仍在应用层直接使用 ORM 模型。

**修复实施步骤**

1. 为 User 添加 `_to_entity()` 转换和领域实体映射
2. 为 ChatSession 添加 `_to_entity()` 转换
3. 为 ChatMessage 添加 `_to_entity()` 转换
4. 为 Document 添加 `_to_entity()` 转换
5. 更新应用层代码，使用领域实体替代 ORM 模型
6. 更新相关测试

**验收标准**

- [ ] 所有 ORM 模型都有对应的 `_to_entity()` 方法
- [ ] 应用层代码不再直接使用 ORM 模型属性
- [ ] `uv run pytest backend/tests/unit/ -q` 失败数 ≤ 3
- [ ] 领域层无 SQLAlchemy 导入

---

#### TASK-021: PromptCache 一致性与安全日志

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-M2, SEC-M3, SEC-M8 |
| **所属模块** | backend/app/infra/cache/, backend/app/infra/providers/ |
| **严重程度** | Medium |
| **风险评分** | 6 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. `PromptCache` 的 `get()` 使用锁但 `refresh()`/`invalidate()` 不使用，存在竞态条件
2. `rerank.py:223` 日志中暴露 API 密钥最后4位
3. `deps.py:164-166` `get_optional_user` 中 Redis 异常静默忽略

**修复实施步骤**

1. 为 `PromptCache.refresh()` 和 `PromptCache.invalidate()` 添加 `async with self._lock`
2. 修改 `rerank.py:223`：将 `'***' + settings.RERANK_API_KEY[-4:]` 改为 `'[configured]' if settings.RERANK_API_KEY else '[not set]'`
3. 在 `deps.py:164-166` 添加 `logger.warning(f"Redis error during optional user check: {e}")`

**验收标准**

- [ ] `PromptCache` 所有公共方法使用锁
- [ ] 日志中不包含 API 密钥的任何部分
- [ ] Redis 异常有日志记录
- [ ] `uv run pytest backend/tests/unit/test_prompt_cache.py -v` 通过

---

#### TASK-022: 前端 Composable 状态管理统一

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-M3 |
| **所属模块** | frontend/src/composables/ |
| **严重程度** | Medium |
| **风险评分** | 6 |
| **预计工时** | 6h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`useAuth` 和 `useChat` 使用模块级 ref（全局共享），`useExhibits` 和 `useCurator` 使用函数内 ref（每次新建），`useDocuments` 混合使用。状态共享行为不一致。

**修复实施步骤**

1. 将 `useExhibits` 的 ref 提升为模块级，实现全局共享
2. 将 `useCurator` 的 ref 提升为模块级
3. 统一 `useDocuments` 的状态管理方式
4. 在每个 Composable 中添加 `reset()` 方法用于状态清理
5. 添加 JSDoc 注释说明状态共享策略

**验收标准**

- [ ] 所有 Composable 使用统一的模块级 ref 模式
- [ ] 同一 Composable 在不同组件中调用返回相同状态
- [ ] `npm run test` 全部通过
- [ ] 无状态共享导致的 UI 不一致问题

---

#### TASK-023: 密码策略增强

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-M7 |
| **所属模块** | backend/app/api/auth.py |
| **严重程度** | Medium |
| **风险评分** | 6 |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

密码验证规则仅要求大写字母、小写字母和数字，未要求特殊字符，密码复杂度策略偏弱。

**修复实施步骤**

1. 在 `RegisterRequest` 的 `password` 字段验证中添加特殊字符要求
2. 更新正则表达式：从当前规则添加 `[^a-zA-Z0-9]` 检查
3. 更新前端注册表单的密码提示文案
4. 添加密码强度指示器（可选）

**验收标准**

- [ ] 密码必须包含至少一个特殊字符
- [ ] 前端注册表单提示更新
- [ ] `uv run pytest backend/tests/contract/test_auth_api.py -v` 通过
- [ ] 新增密码策略的单元测试

---

#### TASK-024: 前端日志安全与 API 重试

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-M6, PERF-M3 |
| **所属模块** | frontend/src/utils/logger.js, frontend/src/api/index.js |
| **严重程度** | Medium |
| **风险评分** | 5 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. 前端 `logger.js` 的 `error()` 在生产环境也输出到控制台
2. 前端 API 默认不重试（`retries: 0`）

**修复实施步骤**

1. 修改 `logger.js`：`error()` 方法在生产环境过滤敏感信息（URL 参数中的 token、API 密钥等）
2. 在 `api/index.js` 中为关键 API 调用配置重试：
   - 认证相关：`retries: 1`
   - 聊天相关：`retries: 2`
   - 文档上传：不重试（非幂等）
3. 添加 429 状态码的指数退避重试支持

**验收标准**

- [ ] 生产环境控制台不包含敏感信息
- [ ] 关键 API 调用配置了合理的重试次数
- [ ] 429 响应码触发退避重试
- [ ] `npm run test` 全部通过

---

#### TASK-025: 数据库索引优化

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-M4, PERF-L4 |
| **所属模块** | backend/app/infra/postgres/ |
| **严重程度** | Medium |
| **风险评分** | 5 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. `chat_messages` 表缺少 `created_at` 索引，消息排序依赖文件排序
2. `documents` 表缺少 `created_at` 索引
3. `document_repository.update_status` 执行两次查询可合并

**修复实施步骤**

1. 创建 Alembic 迁移：为 `chat_messages.created_at` 添加索引
2. 创建 Alembic 迁移：为 `documents.created_at` 添加索引
3. 重构 `document_repository.update_status`：使用 `UPDATE ... RETURNING` 合并两次查询为一次
4. 验证迁移在 SQLite（测试）和 PostgreSQL（生产）上均可执行

**验收标准**

- [ ] `chat_messages.created_at` 有索引
- [ ] `documents.created_at` 有索引
- [ ] `update_status` 仅执行1次数据库查询
- [ ] `uv run pytest backend/tests/unit/test_repositories.py -v` 通过
- [ ] Alembic 迁移可正常执行和回滚

---

#### TASK-026: Embedding 批量调用优化

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-M6 |
| **所属模块** | backend/app/infra/providers/embedding.py |
| **严重程度** | Medium |
| **风险评分** | 5 |
| **预计工时** | 4h |
| **前置依赖** | TASK-004 |
| **负责人** | 待分配 |

**问题描述**

`embed_batch` 逐个文本请求 embedding，而非使用 Ollama 的批量 API，大量文本时 HTTP 开销大。

**修复实施步骤**

1. 修改 `embed_batch` 使用 Ollama 的批量 embedding API（`/api/embed` 支持多文本输入）
2. 保留 Semaphore 并发控制，但每个请求包含多个文本
3. 添加批量大小配置参数（`batch_size: int = 20`）
4. 处理批量请求中部分失败的情况

**验收标准**

- [ ] 100 个文本的 embedding 请求次数从 100 降至 5-10
- [ ] 文档摄取时间减少 50% 以上
- [ ] `uv run pytest backend/tests/unit/test_embedding_provider.py -v` 通过
- [ ] 批量请求中部分失败时正确处理

---

#### TASK-027: 前端生产环境日志门控

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-M6 |
| **所属模块** | frontend/src/utils/logger.js |
| **严重程度** | Medium |
| **风险评分** | 5 |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

前端 `logger.js` 的 `error()` 在生产环境也输出到控制台，可能泄露敏感信息。

**修复实施步骤**

1. 修改 `logger.js`：`error()` 方法在生产环境过滤敏感信息
2. 添加 URL 参数脱敏函数：移除 `token`、`key`、`secret` 等参数
3. 在生产环境将 `error()` 输出发送到远程日志服务（可选）

**验收标准**

- [ ] 生产环境控制台不包含 token、API 密钥等敏感信息
- [ ] 开发环境日志输出不受影响
- [ ] `npm run test` 全部通过

---

#### TASK-028: HTTPS/TLS 配置指导

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-M5 |
| **所属模块** | 项目文档 / 配置 |
| **严重程度** | Medium |
| **风险评分** | 4 |
| **预计工时** | 3h |
| **前置依赖** | TASK-015 |
| **负责人** | 待分配 |

**问题描述**

项目无 HTTPS/TLS 服务器配置，依赖外部反向代理，但未提供配置指导。

**修复实施步骤**

1. 编写 Nginx 反向代理配置模板（含 TLS、HSTS、安全头部）
2. 添加 HSTS 中间件到 FastAPI 应用
3. 在 README 中添加 HTTPS 部署指南
4. 添加安全响应头部中间件（X-Content-Type-Options, X-Frame-Options 等）

**验收标准**

- [ ] Nginx 配置模板可用
- [ ] FastAPI 应用添加 HSTS 和安全头部
- [ ] 部署文档包含 HTTPS 配置步骤
- [ ] 安全头部测试通过

---

### Phase 4: P3 长期优化

---

#### TASK-029: 前端虚拟滚动

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-M2, PERF-L1 |
| **所属模块** | frontend/src/components/ |
| **严重程度** | Medium |
| **风险评分** | 6 |
| **预计工时** | 8h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

ChatPanel 和 ExhibitList 使用 `v-for` 渲染完整列表，长对话/大量展品时 DOM 节点过多，渲染卡顿。

**修复实施步骤**

1. 评估虚拟滚动库选型（`vue-virtual-scroller` 或 `@tanstack/vue-virtual`）
2. 为 ChatPanel 消息列表实现虚拟滚动
3. 为 ExhibitList 展品列表实现虚拟滚动
4. 确保虚拟滚动与现有交互（滚动到底部、加载更多）兼容

**验收标准**

- [ ] 1000 条消息时 DOM 节点数 < 50
- [ ] 500 个展品时 DOM 节点数 < 30
- [ ] 滚动流畅度 ≥ 55fps
- [ ] 新消息自动滚动到底部功能正常
- [ ] `npm run test` 全部通过

---

#### TASK-030: Token 刷新机制

| 属性 | 值 |
|------|-----|
| **审计编号** | SEC-L1, SEC-L2 |
| **所属模块** | backend/app/api/auth.py, backend/app/infra/security/ |
| **严重程度** | Low |
| **风险评分** | 4 |
| **预计工时** | 12h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

无 refresh token 机制，JWT 过期后用户必须重新登录。默认过期时间 1440 分钟（24小时）过长。

**修复实施步骤**

1. 在 `jwt_handler.py` 中实现 refresh token 生成和验证
2. 在 `auth.py` 中添加 `/api/v1/auth/refresh` 端点
3. 修改登录响应：同时返回 access_token（短期，60分钟）和 refresh_token（长期，7天）
4. 在 Redis 中存储 refresh token 的映射关系
5. 前端实现自动刷新：access_token 过期前5分钟自动调用 refresh 端点
6. 修改 `.env.example`：`JWT_EXPIRE_MINUTES=60`，新增 `JWT_REFRESH_EXPIRE_DAYS=7`

**验收标准**

- [ ] access_token 有效期 60 分钟
- [ ] refresh_token 有效期 7 天
- [ ] 前端自动刷新 token，用户无感知
- [ ] refresh_token 只能使用一次（轮换机制）
- [ ] `uv run pytest backend/tests/contract/test_auth_api.py -v` 通过
- [ ] `npm run test` 全部通过

---

#### TASK-031: ORM-领域实体映射完善（剩余实体）

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-M1（延续） |
| **所属模块** | backend/app/infra/postgres/ |
| **严重程度** | Low |
| **风险评分** | 4 |
| **预计工时** | 6h |
| **前置依赖** | TASK-020 |
| **负责人** | 待分配 |

**问题描述**

TASK-020 完成主要实体的映射后，仍有 IngestionJob、Prompt、PromptVersion 等次要实体需要映射。

**修复实施步骤**

1. 为 IngestionJob 添加 `_to_entity()` 转换
2. 为 Prompt 和 PromptVersion 添加 `_to_entity()` 转换
3. 为 TourPath 添加 `_to_entity()` 转换
4. 更新所有使用这些 ORM 模型的应用层代码

**验收标准**

- [ ] 所有 ORM 模型都有对应的领域实体转换
- [ ] 应用层代码完全不直接使用 ORM 模型
- [ ] `uv run pytest backend/tests/ -q --ignore=backend/tests/performance -k "not e2e"` 失败数 ≤ 3

---

#### TASK-032: 领域实体行为封装

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-M4 |
| **所属模块** | backend/app/domain/entities.py |
| **严重程度** | Low |
| **风险评分** | 4 |
| **预计工时** | 6h |
| **前置依赖** | TASK-020 |
| **负责人** | 待分配 |

**问题描述**

除 `IngestionJob` 外，其他领域实体直接修改属性而非通过方法，违反 DDD 原则。

**修复实施步骤**

1. 为 `Exhibit` 添加 `update_details()`、`deactivate()` 方法
2. 为 `VisitorProfile` 添加 `update_preferences()` 方法
3. 为 `ChatSession` 添加 `add_message()`、`close()` 方法
4. 为 `Document` 添加 `update_status()` 方法
5. 将实体属性修改迁移到方法调用

**验收标准**

- [ ] 领域实体状态变更通过方法调用
- [ ] 实体属性不直接被外部修改（考虑使用 `@property` + 私有属性）
- [ ] `uv run pytest backend/tests/unit/test_domain_entities.py -v` 通过

---

#### TASK-033: Settings 单例优化

| 属性 | 值 |
|------|-----|
| **审计编号** | ARCH-L2 |
| **所属模块** | backend/app/config/settings.py |
| **严重程度** | Low |
| **风险评分** | 3 |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`get_settings()` 每次调用创建新实例，浪费资源且可能导致配置不一致。

**修复实施步骤**

1. 使用 `functools.lru_cache` 装饰 `get_settings()`
2. 或使用模块级变量缓存实例
3. 添加 `reset_settings()` 函数用于测试清理

**验收标准**

- [ ] `get_settings()` 返回同一实例（`is` 比较为 True）
- [ ] 测试中可通过 `reset_settings()` 重置
- [ ] `uv run pytest backend/tests/unit/test_config.py -v` 通过

---

#### TASK-034: 展品图片懒加载

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-L2 |
| **所属模块** | frontend/src/components/exhibits/ |
| **严重程度** | Low |
| **风险评分** | 3 |
| **预计工时** | 3h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

展品图片无懒加载，首屏加载大量图片影响性能。

**修复实施步骤**

1. 使用 `IntersectionObserver` 实现图片懒加载
2. 或使用 Vue 3 的 `v-lazy` 指令库
3. 添加加载占位符和错误回退

**验收标准**

- [ ] 首屏仅加载可见区域的图片
- [ ] 滚动时图片按需加载
- [ ] 图片加载失败有占位符
- [ ] `npm run test` 全部通过

---

#### TASK-035: Vite 构建优化

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-L3 |
| **所属模块** | frontend/ |
| **严重程度** | Low |
| **风险评分** | 3 |
| **预计工时** | 4h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

Vite 构建配置简单，未配置代码分割、压缩优化等。

**修复实施步骤**

1. 配置 `build.rollupOptions.output.manualChunks`：将 vue、element-plus 等大依赖分离
2. 配置 `build.cssCodeSplit: true`
3. 启用 `build.minify: 'terser'`（或默认 esbuild）
4. 配置 `build.sourcemap: true`（仅生产环境）
5. 分析构建产物大小：`rollup-plugin-visualizer`

**验收标准**

- [ ] 首屏 JS 体积 < 200KB（gzip 后）
- [ ] Element Plus 等大依赖独立 chunk
- [ ] Lighthouse 性能评分 ≥ 85
- [ ] `npm run build` 成功且无警告

---

#### TASK-036: pytest 配置优化

| 属性 | 值 |
|------|-----|
| **审计编号** | CODE-6, CODE-7 |
| **所属模块** | backend/tests/ |
| **严重程度** | Low |
| **风险评分** | 2 |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

1. `@pytest.mark.integration` 未注册导致警告
2. Locust `TestConfig` dataclass 被 pytest 误识别为测试类

**修复实施步骤**

1. 在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 中注册自定义 mark：
   ```toml
   markers = ["integration: marks tests as integration tests"]
   ```
2. 在 `backend/tests/performance/test_users.py` 中重命名 `TestConfig` 为 `LoadTestConfig`，避免 pytest 收集

**验收标准**

- [ ] `uv run pytest backend/tests/ -q --ignore=backend/tests/performance` 无 PytestUnknownMarkWarning
- [ ] `TestConfig` 不再被 pytest 收集
- [ ] 测试运行无警告

---

#### TASK-037: PromptCache LRU 淘汰策略

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-L5 |
| **所属模块** | backend/app/infra/cache/prompt_cache.py |
| **严重程度** | Low |
| **风险评分** | 2 |
| **预计工时** | 3h |
| **前置依赖** | TASK-021 |
| **负责人** | 待分配 |

**问题描述**

`PromptCache` 的 `_cache` 字典无大小限制，理论上可能内存泄漏。

**修复实施步骤**

1. 使用 `collections.OrderedDict` 替代 `dict`，实现 LRU 淘汰
2. 添加 `max_size` 配置参数（默认 100）
3. 在 `get()` 中将访问的条目移到末尾
4. 在 `set()` 中检查大小并淘汰最久未使用的条目

**验收标准**

- [ ] PromptCache 最大容量可配置
- [ ] 超出容量时自动淘汰最久未使用的条目
- [ ] `uv run pytest backend/tests/unit/test_prompt_cache.py -v` 通过

---

#### TASK-038: document_repository 查询合并

| 属性 | 值 |
|------|-----|
| **审计编号** | PERF-L4 |
| **所属模块** | backend/app/infra/postgres/adapters/document_repository.py |
| **严重程度** | Low |
| **风险评分** | 2 |
| **预计工时** | 2h |
| **前置依赖** | 无 |
| **负责人** | 待分配 |

**问题描述**

`update_status` 方法先查询 Document，再单独查询 IngestionJob，两次查询可合并。

**修复实施步骤**

1. 使用 `UPDATE ... RETURNING` 合并 Document 的查询和更新
2. 使用 `selectinload` 或 `joinedload` 预加载 IngestionJob 关系
3. 或使用单次查询 + CTE (Common Table Expression) 完成所有操作

**验收标准**

- [ ] `update_status` 仅执行1次数据库往返
- [ ] `uv run pytest backend/tests/unit/test_repositories.py -v` 通过
- [ ] 功能行为不变

---

## 四、任务依赖关系图

```
Phase 1 (P0) — 无外部依赖，可并行执行
├── TASK-001 ─── 无依赖
├── TASK-002 ─── 无依赖
├── TASK-003 ─── 无依赖
├── TASK-004 ─── 无依赖
├── TASK-005 ─── 无依赖
└── TASK-006 ─── 依赖 TASK-005

Phase 2 (P1) — 部分依赖 Phase 1
├── TASK-007 ─── 无依赖
├── TASK-008 ─── 无依赖（但建议 Phase 1 完成后开始）
├── TASK-009 ─── 依赖 TASK-008
├── TASK-010 ─── 依赖 TASK-008
├── TASK-011 ─── 依赖 TASK-008
├── TASK-012 ─── 无依赖
├── TASK-013 ─── 无依赖
├── TASK-014 ─── 无依赖
├── TASK-015 ─── 无依赖
└── TASK-016 ─── 依赖 TASK-008

Phase 3 (P2) — 依赖 Phase 2
├── TASK-017 ─── 无依赖
├── TASK-018 ─── 依赖 TASK-010
├── TASK-019 ─── 无依赖
├── TASK-020 ─── 依赖 TASK-008
├── TASK-021 ─── 无依赖
├── TASK-022 ─── 无依赖
├── TASK-023 ─── 无依赖
├── TASK-024 ─── 无依赖
├── TASK-025 ─── 无依赖
├── TASK-026 ─── 依赖 TASK-004
├── TASK-027 ─── 无依赖
└── TASK-028 ─── 依赖 TASK-015

Phase 4 (P3) — 依赖 Phase 3
├── TASK-029 ─── 无依赖
├── TASK-030 ─── 无依赖
├── TASK-031 ─── 依赖 TASK-020
├── TASK-032 ─── 依赖 TASK-020
├── TASK-033 ─── 无依赖
├── TASK-034 ─── 无依赖
├── TASK-035 ─── 无依赖
├── TASK-036 ─── 无依赖
├── TASK-037 ─── 依赖 TASK-021
└── TASK-038 ─── 无依赖

关键路径: TASK-008 → TASK-009 → TASK-010 → TASK-018
         TASK-008 → TASK-020 → TASK-031/032
```

---

## 五、风险管理

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 六角架构重构引入回归 | 高 | 高 | 每个服务独立重构，逐步合入；充分测试覆盖 |
| chat_service 拆分影响 SSE 流式功能 | 中 | 高 | 拆分前确保流式测试覆盖；拆分后端到端验证 |
| 文件上传流式改造影响现有功能 | 中 | 中 | 保留原有 API 接口不变；分块处理对调用方透明 |
| Token 刷新机制需要前后端协同 | 中 | 中 | 前后端同步开发；定义清晰的 API 契约 |
| Ruff 自动修复引入语义变化 | 低 | 中 | 自动修复后运行完整测试套件；代码审查 |
| 数据库迁移在生产环境失败 | 低 | 高 | 迁移脚本先在 staging 验证；保留回滚路径 |

---

## 六、验收总则

### 通用验收标准（适用于所有任务）

1. **功能验证**：所有相关测试通过（`uv run pytest` / `npm run test`）
2. **代码质量**：
   - `uv run ruff check backend/app/` 无新增错误
   - `uv run mypy backend/app/ --ignore-missing-imports` 无新增错误
3. **无回归**：修复前通过的测试在修复后仍通过
4. **文档更新**：涉及 API 变更或配置变更的，更新相关文档

### 阶段验收门禁

| 阶段 | 门禁条件 |
|------|---------|
| Phase 1 完成 | 0 个 Critical 问题；单元测试全绿；安全扫描无 Critical 发现 |
| Phase 2 完成 | 0 个 High 安全问题；架构测试覆盖所有应用服务；MyPy 错误 < 50 |
| Phase 3 完成 | MyPy 错误 < 20；Ruff 错误 = 0；速率限制原子化验证通过 |
| Phase 4 完成 | Lighthouse 评分 ≥ 85；Token 刷新可用；构建产物优化达标 |

### 持续监控指标

| 指标 | 当前值 | 目标值 | 监控方式 |
|------|--------|--------|---------|
| 单元测试通过率 | 98.7% (541/548) | 100% | CI |
| MyPy 类型错误 | 146 | < 20 | CI |
| Ruff 代码规范错误 | 136 | 0 | CI |
| Critical 安全问题 | 3 | 0 | Bandit + 审计 |
| 测试覆盖率 | ≥70% | ≥80% | pytest-cov |
| 首屏 JS 体积 (gzip) | 未知 | < 200KB | Lighthouse |
