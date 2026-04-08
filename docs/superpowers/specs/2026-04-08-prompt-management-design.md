# Prompt管理系统设计文档

## 概述

将项目中硬编码的prompt迁移到数据库管理系统，支持版本化、热重载和管理员API修改。

## 目标

1. **集中管理** - 所有prompt存储在PostgreSQL数据库，统一管理
2. **版本控制** - 完整版本历史，支持回滚和对比
3. **热重载** - 修改后实时生效，无需重启应用
4. **管理接口** - 提供管理员API进行CRUD操作

## 架构设计

### 数据库设计

#### 表 `prompts`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| key | VARCHAR(100) | 唯一标识，如 `rag_answer_generation` |
| name | VARCHAR(255) | 显示名称 |
| description | TEXT | 用途说明 |
| category | VARCHAR(50) | 分类：rag/curator/query_transform/reflection |
| content | TEXT | prompt内容，支持模板变量 |
| variables | JSON | 模板变量列表及说明 |
| is_active | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### 表 `prompt_versions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(36) | 主键，UUID |
| prompt_id | VARCHAR(36) | 外键，关联prompts表 |
| version | INTEGER | 版本号，每个prompt内递增 |
| content | TEXT | 该版本的prompt内容 |
| changed_by | VARCHAR(36) | 修改人user_id |
| change_reason | TEXT | 修改原因 |
| created_at | TIMESTAMP | 创建时间 |

索引：
- `idx_prompt_versions_prompt_id` ON (prompt_id)
- `idx_prompt_versions_prompt_version` ON (prompt_id, version) UNIQUE

### 应用层架构

```
backend/app/
├── domain/
│   ├── entities.py              # 新增Prompt实体
│   └── value_objects.py         # 新增PromptKey值对象
├── application/
│   └── prompt_service.py        # Prompt业务逻辑
├── infra/
│   ├── postgres/
│   │   ├── models.py            # 新增Prompt和PromptVersion模型
│   │   └── prompt_repository.py # 数据库操作
│   └── cache/
│       └── prompt_cache.py      # 内存缓存管理
├── api/
│   ├── admin/
│   │   └── prompts.py           # 管理员API端点
│   └── deps.py                  # 新增PromptCacheDep
```

### 热重载机制

```
┌─────────────────┐
│   Admin API     │
│  PUT /prompts   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PromptService   │
│ update_prompt() │
└────────┬────────┘
         │
         ├──► ┌─────────────────┐
         │    │   PostgreSQL    │
         │    │  - prompts      │
         │    │  - prompt_versions │
         │    └─────────────────┘
         │
         └──► ┌─────────────────┐
              │  PromptCache    │
              │  (内存单例)      │
              │  - 自动刷新      │
              └─────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  使用方         │
              │  - RAGAgent     │
              │  - CuratorAgent │
              │  - QueryTransformer │
              └─────────────────┘
```

**实现细节：**
- `PromptCache` 作为全局单例，启动时加载所有活跃prompt
- `PromptService.update_prompt()` 更新数据库后调用 `cache.refresh(key)`
- 提供 `/admin/prompts/{key}/reload` 端点手动刷新

### API设计

#### 管理员端点（需要admin角色）

```
GET    /admin/prompts
  - 列出所有prompt
  - 支持category过滤

GET    /admin/prompts/{key}
  - 获取prompt详情
  - 包含当前版本信息

PUT    /admin/prompts/{key}
  - 更新prompt内容
  - 请求体：{ "content": "...", "change_reason": "..." }
  - 自动创建新版本并刷新缓存

GET    /admin/prompts/{key}/versions
  - 获取版本历史列表

GET    /admin/prompts/{key}/versions/{version}
  - 获取指定版本详情

POST   /admin/prompts/{key}/versions/{version}/rollback
  - 回滚到指定版本
  - 自动创建新版本记录

POST   /admin/prompts/{key}/reload
  - 手动刷新缓存

POST   /admin/prompts/reload-all
  - 刷新所有prompt缓存
```

#### 内部使用接口

```python
class PromptService:
    async def get_prompt(key: str) -> Prompt
        # 从缓存获取，缓存未命中则从数据库加载

    async def render_prompt(key: str, variables: dict) -> str
        # 获取prompt并渲染模板变量
```

### Prompt迁移清单

| Key | 来源文件 | 分类 | 模板变量 |
|-----|----------|------|----------|
| `rag_answer_generation` | agents.py:226 | rag | context, query |
| `curator_system` | curator_agent.py:74 | curator | - |
| `narrative_generation` | curator_tools.py:322 | curator | exhibit_name, exhibit_info, level_guidance, style_guidance |
| `query_rewrite` | query_transform.py:30 | query_transform | conversation_history, query |
| `query_step_back` | query_transform.py:85 | query_transform | query |
| `query_hyde` | query_transform.py:92 | query_transform | query |
| `query_multi` | query_transform.py:99 | query_transform | query |
| `reflection_beginner` | reflection_prompts.py:28 | reflection | - |
| `reflection_intermediate` | reflection_prompts.py:36 | reflection | - |
| `reflection_expert` | reflection_prompts.py:45 | reflection | - |
| `reflection_bronze` | reflection_prompts.py:55 | reflection | - |
| `reflection_painting` | reflection_prompts.py:63 | reflection | - |
| `reflection_ceramic` | reflection_prompts.py:70 | reflection | - |
| `narrative_style_storytelling` | reflection_prompts.py:81 | reflection | - |
| `narrative_style_academic` | reflection_prompts.py:85 | reflection | - |
| `narrative_style_interactive` | reflection_prompts.py:89 | reflection | - |

### 模板变量

使用 Python format 风格的变量替换：

```python
prompt = await prompt_service.render_prompt(
    "rag_answer_generation",
    {"context": context, "query": query}
)
```

变量格式：`{variable_name}`

## 迁移计划

### 阶段一：基础设施

1. 创建数据库模型和迁移脚本
2. 实现 `PromptRepository`
3. 实现 `PromptCache`
4. 实现 `PromptService`

### 阶段二：API和管理端点

1. 创建管理员API端点
2. 添加权限验证（admin角色）
3. 实现版本历史和回滚

### 阶段三：数据迁移

1. 编写迁移脚本，将现有硬编码prompt导入数据库
2. 创建初始版本记录

### 阶段四：集成

1. 修改 `RAGAgent` 使用 `PromptService`
2. 修改 `CuratorAgent` 使用 `PromptService`
3. 修改 `QueryTransformer` 使用 `PromptService`
4. 修改 `ReflectionPromptTool` 使用 `PromptService`

### 阶段五：测试和文档

1. 单元测试
2. 契约测试
3. 集成测试
4. API文档

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| Prompt不存在 | 抛出 `PromptNotFoundError`，返回404 |
| 模板变量缺失 | 抛出 `PromptVariableError`，记录日志 |
| 数据库写入失败 | 事务回滚，缓存保持旧值 |
| 缓存刷新失败 | 记录日志，不影响数据库更新 |

## 性能考虑

- 缓存命中时：O(1) 内存访问
- 缓存未命中时：单次数据库查询
- 更新操作：写数据库 + 刷新缓存，约10-50ms
- 版本查询：支持分页，避免大量历史数据

## 安全考虑

- 管理端点需要admin角色验证
- prompt内容不做HTML转义（LLM输入）
- 变量值需要做基本的注入检查
- 操作日志记录修改人和原因
