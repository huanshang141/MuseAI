# MuseAI V2 开发工作交接文档

**生成日期**: 2026-04-04  
**当前状态**: Phase 0 完成，Phase 1 进行中  
**总进度**: 8/20 任务完成 (40%)

---

## 一、已完成工作

### Phase 0: 脚手架与基线 (Week 1) ✅

| 任务 | 交付物 | 测试 | 状态 |
|------|--------|------|------|
| Task 1: Domain Models | entities.py, value_objects.py, exceptions.py | 8/8 通过 | ✅ |
| Task 2: Configuration Model | settings.py | 2/2 通过 | ✅ |
| Task 3: Database Models | models.py (SQLAlchemy) | 5/5 通过 | ✅ |
| Task 4: Database Session | database.py (async) | 1/1 通过 | ✅ |
| Task 5: Health Check | health.py | 2/2 通过 | ✅ |
| Task 6: CI Configuration | ci.yml (GitHub Actions) | - | ✅ |

### Phase 1: 摄入与检索内核 (Week 2-3) 🔄

| 任务 | 交付物 | 测试 | 状态 |
|------|--------|------|------|
| Task 7: Text Chunking | chunking.py | 5/5 通过 | ✅ |
| Task 8: Embedding Provider | embedding.py | 2/2 通过 | ✅ |
| Task 9: Elasticsearch Client | - | - | ⏳ 待执行 |
| Task 10: RRF Fusion | - | - | ⏳ 待执行 |
| Task 11: Document Upload API | - | - | ⏳ 待执行 |

### 当前测试统计

```
总计: 24/24 通过 (100%)
- 单元测试: 22 个
- 契约测试: 2 个
```

---

## 二、待处理的代码审查意见

### 🔴 重要 (建议在生产环境前处理)

#### Task 1: Domain Models
**无重要问题**

#### Task 2: Configuration Model
**无重要问题**

#### Task 3: Database Models
1. **datetime.utcnow 已弃用**
   - 位置: `models.py` (多处)
   - 问题: 使用 `datetime.utcnow()` 在 Python 3.12+ 中已弃用
   - 修复: 改用 `datetime.now(timezone.utc)`

#### Task 4: Database Session Management
1. **Engine 生命周期未管理**
   - 位置: `database.py:6`
   - 问题: `create_async_engine()` 创建的 engine 未关闭，可能导致连接池泄漏
   - 修复: 在应用关闭时调用 `engine.dispose()`

2. **未测试事务行为**
   - 位置: `test_db_session.py`
   - 问题: 未验证 commit on success 和 rollback on exception
   - 修复: 添加测试用例验证事务行为

#### Task 5: Health Check Endpoint
1. **Readiness Check 返回静态 Mock 数据**
   - 位置: `health.py:11-14`
   - 问题: `/ready` 端点返回硬编码的 `"unknown"`，不检查实际依赖状态
   - 修复: 实现真实的数据库、ES、Redis 健康检查

2. **缺少返回类型注解**
   - 位置: `health.py:6-7`, `11-12`
   - 问题: 端点函数缺少 `-> dict` 返回类型
   - 修复: 添加类型注解

3. **健康检查应返回 HTTP 503**
   - 位置: `health.py:11-14`
   - 问题: 即使依赖失败也返回 HTTP 200
   - 修复: 依赖失败时返回 503 Service Unavailable

#### Task 6: CI Configuration
1. **缺少 Job 依赖**
   - 位置: `ci.yml`
   - 问题: test-unit 和 test-contract 与 lint 并行运行，lint 失败时浪费资源
   - 修复: 添加 `needs: lint` 依赖

2. **未配置缓存**
   - 位置: `ci.yml`
   - 问题: 每次运行都重新安装依赖
   - 修复: 添加 `enable-cache: true` 到 uv setup

3. **缺少超时设置**
   - 位置: `ci.yml`
   - 问题: 默认 6 小时超时
   - 修复: 添加 `timeout-minutes: 10`

#### Task 7: Text Chunking Service
1. **Overlap 测试逻辑有缺陷**
   - 位置: `test_chunking.py:40`
   - 问题: `assert overlap_found or len(chunks) == 1` 总是通过单 chunk 情况
   - 修复: 确保测试使用足够大的文本产生多 chunks，然后验证 overlap

2. **死代码 - 未使用变量**
   - 位置: `chunking.py:59`
   - 问题: `chunk_index` 变量未使用
   - 修复: 删除 `chunk_index` 相关代码

#### Task 8: Embedding Provider
1. **顺序批处理效率低**
   - 位置: `embedding.py:26-30`
   - 问题: `embed_batch` 顺序处理，速度慢
   - 修复: 使用 `asyncio.gather()` 并发处理

2. **缺少超时配置**
   - 位置: `embedding.py:20`
   - 问题: 超时时间硬编码为 60 秒
   - 修复: 添加可配置的超时参数

3. **HTTP Client 未复用**
   - 位置: `embedding.py:18`
   - 问题: 每次调用都创建新 client
   - 修复: 将 client 存储为实例变量

4. **dims 参数未使用**
   - 位置: `embedding.py:15`
   - 问题: 存储了 dims 但未用于验证
   - 修复: 验证返回的 embedding 维度是否匹配

---

### 🟡 次要 (优化建议)

#### Task 3: Database Models
- 缺少复合索引 `(session_id, created_at)` 用于消息排序
- `status` 字段可使用 Enum 提高类型安全
- 缺少 docstrings

#### Task 4: Database Session
- 缺少返回类型注解 `-> AsyncIterator[AsyncSession]`
- `postgres/__init__.py` 未导出公共 API

#### Task 5: Health Check
- 未使用 Pydantic Response Models
- 缺少 docstrings

#### Task 6: CI
- Python 版本未固定到 patch 版本
- 缺少 artifact 上传

#### Task 7: Chunking
- 缺少空文本测试
- 缺少输入验证 (负数、零值检查)
- 缺少单 chunk 测试

#### Task 8: Embedding
- 缺少错误场景测试 (HTTP 错误、格式错误响应)
- 缺少空 batch 测试

---

## 三、接下来应完成的工作

### Phase 1: 摄入与检索内核 (Week 2-3)

#### 立即执行 (高优先级)

**Task 9: Elasticsearch Client** ⏰ 预计 1-2 小时
- 创建 `backend/app/infra/elasticsearch/client.py`
- 实现功能:
  - `create_index(dims)` - 创建带 mapping 的索引
  - `index_chunk()` - 索引文档块
  - `search_dense()` - 向量检索
  - `search_bm25()` - 关键词检索
  - `delete_by_document()` - 按文档删除
- 创建测试 `test_es_client.py`

**Task 10: RRF Fusion Algorithm** ⏰ 预计 1 小时
- 创建 `backend/app/application/retrieval.py`
- 实现 RRF (Reciprocal Rank Fusion) 算法
- 公式: `score(d) = Σ 1/(k + rank_i(d))`，k=60
- 创建测试 `test_rag_fusion.py`

**Task 11: Document Upload API** ⏰ 预计 2-3 小时
- 创建 `backend/app/api/documents.py`
- 创建 `backend/app/application/document_service.py`
- 实现功能:
  - POST /documents/upload - 上传文档
  - GET /documents - 文档列表
  - GET /documents/{id} - 文档详情
  - GET /documents/{id}/status - 摄入状态
  - DELETE /documents/{id} - 删除文档
- 创建测试 `test_documents_api.py`

### Phase 2: 多轮与流式 (Week 4-5)

#### 按计划执行

**Task 12: LLM Provider**
- OpenAI-compatible API 客户端
- 流式生成支持

**Task 13: Chat Session API**
- 会话管理端点
- 消息历史查询

**Task 14: SSE Streaming**
- Server-Sent Events 实现
- 流式中断处理

**Task 15: Multi-turn State Machine**
- 多轮对话状态机
- Query transform 策略

### Phase 3: 集成与部署 (Week 6)

**Task 16-20: 集成测试、认证、缓存、E2E**

---

## 四、技术债务追踪

### 高优先级债务 (生产环境前必须解决)

| 债务项 | 来源 | 影响 | 建议解决时间 |
|--------|------|------|-------------|
| Health Check 静态数据 | Task 5 | 无法监控真实健康状态 | Phase 1 结束 |
| Embedding 顺序批处理 | Task 8 | 文档摄入性能差 | Phase 1 结束 |
| datetime.utcnow 弃用 | Task 3 | Python 3.12+ 兼容性 | Phase 1 结束 |
| Engine 生命周期 | Task 4 | 连接池泄漏 | Phase 2 开始 |

### 中等优先级债务 (建议在下个 Phase 处理)

| 债务项 | 来源 | 影响 | 建议解决时间 |
|--------|------|------|-------------|
| CI 缓存配置 | Task 6 | 构建速度慢 | Phase 1 结束 |
| 事务行为测试 | Task 4 | 潜在数据一致性风险 | Phase 2 开始 |
| 输入验证 | Task 7 | 无效输入可能导致错误 | Phase 2 开始 |

---

## 五、关键决策记录

### 已做决策

1. **TDD 开发流程**: 所有任务遵循 RED-GREEN-REFACTOR 循环
2. **Subagent-Driven Development**: 每个任务分派独立子代理实现
3. **代码审查**: 每个任务完成后进行 Spec + Quality 双重审查
4. **技术栈确认**: FastAPI + PostgreSQL + Elasticsearch + Redis + Ollama

### 待做决策

1. **Embedding 并发策略**: 是否使用 `asyncio.gather` 或 `asyncio.Semaphore`?
2. **Health Check 实现方式**: 是否使用 FastAPI 的 `Response` 对象设置状态码?
3. **CI 优化时机**: 是否在本次开发中优化，还是留到后续?

---

## 六、快速恢复指南

### 如需继续开发

```bash
# 1. 确认当前工作目录
cd /home/singer/MuseAI

# 2. 检查当前状态
git log --oneline -10
uv run pytest backend/tests/unit backend/tests/contract -v

# 3. 继续执行 Task 9
# 参考 docs/plans/2026-04-04-museai-v2-implementation.md
```

### 关键文件位置

- **设计文档**: `docs/plans/2026-04-04-museai-v2-design.md`
- **实施计划**: `docs/plans/2026-04-04-museai-v2-implementation.md`
- **当前代码**: `backend/app/`
- **测试代码**: `backend/tests/`
- **CI 配置**: `.github/workflows/ci.yml`

---

## 七、联系人

- **原开发者**: AI Assistant (OpenCode)
- **项目**: MuseAI V2
- **仓库**: `/home/singer/MuseAI`

---

**文档版本**: 1.0  
**最后更新**: 2026-04-04
