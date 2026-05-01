# MuseAI 环境变量配置参考

本文档详细说明 MuseAI 所有环境变量的含义、可选值及配置示例。

配置项通过项目根目录下的 `.env` 文件加载。复制 `.env.example` 作为起点：

```bash
cp .env.example .env
```

---

## 目录

- [基础应用配置](#基础应用配置)
- [安全与认证](#安全与认证)
- [数据库](#数据库)
- [Elasticsearch](#elasticsearch)
- [Redis](#redis)
- [LLM 大语言模型](#llm-大语言模型)
- [Embedding 向量模型](#embedding-向量模型)
- [Rerank 重排序](#rerank-重排序)
- [TTS 语音合成](#tts-语音合成)
- [检索与过滤](#检索与过滤)
- [分块合并](#分块合并)
- [CORS 跨域](#cors-跨域)
- [日志](#日志)
- [速率限制](#速率限制)
- [代理与网络](#代理与网络)
- [管理员](#管理员)

---

## 基础应用配置

### `APP_NAME`

| 项目 | 说明 |
|------|------|
| **含义** | 应用显示名称，用于日志、响应头等标识 |
| **类型** | 字符串 |
| **默认值** | `MuseAI` |

```env
APP_NAME=MuseAI
```

### `APP_ENV`

| 项目 | 说明 |
|------|------|
| **含义** | 运行环境，决定启动行为和安全校验级别 |
| **类型** | 字符串（枚举） |
| **默认值** | `development` |
| **可选值** | `development` / `test` / `local` / `production` |

- `development` — 本地开发，允许宽松的安全默认值
- `test` — 测试环境，常配合内存数据库使用
- `local` — 本地部署，介于开发和生产之间
- `production` — 生产环境，强制要求所有密钥配置，禁止通配符 CORS

```env
APP_ENV=development
```

### `DEBUG`

| 项目 | 说明 |
|------|------|
| **含义** | 是否开启调试模式（详细错误信息、热重载等） |
| **类型** | 布尔值 |
| **默认值** | `False` |
| **可选值** | `true` / `false` |

```env
DEBUG=true
```

---

## 安全与认证

### `JWT_SECRET`

| 项目 | 说明 |
|------|------|
| **含义** | JWT 签名密钥，用于生成和验证用户认证令牌 |
| **类型** | 字符串 |
| **默认值** | 空（生产环境**必须**设置） |
| **要求** | 生产环境长度 ≥ 32 字符 |

生成安全密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

```env
JWT_SECRET=your-very-long-random-secret-string-at-least-32-chars
```

> 当 `ALLOW_INSECURE_DEV_DEFAULTS=true` 且非生产环境时，留空会自动使用不安全的开发默认值。

### `JWT_ALGORITHM`

| 项目 | 说明 |
|------|------|
| **含义** | JWT 签名算法 |
| **类型** | 字符串 |
| **默认值** | `HS256` |
| **可选值** | `HS256` / `HS384` / `HS512` 等 PyJWT 支持的算法 |

```env
JWT_ALGORITHM=HS256
```

### `JWT_EXPIRE_MINUTES`

| 项目 | 说明 |
|------|------|
| **含义** | JWT 令牌有效期（分钟） |
| **类型** | 整数 |
| **默认值** | `60` |

```env
# 示例：令牌 24 小时过期
JWT_EXPIRE_MINUTES=1440
```

### `ALLOW_INSECURE_DEV_DEFAULTS`

| 项目 | 说明 |
|------|------|
| **含义** | 是否允许在非生产环境使用不安全的开发默认值（如默认密钥） |
| **类型** | 布尔值 |
| **默认值** | `False` |
| **可选值** | `true` / `false` |

设为 `true` 时，`JWT_SECRET` 和 `LLM_API_KEY` 留空将自动填充不安全的占位值，仅适用于本地开发调试。

```env
ALLOW_INSECURE_DEV_DEFAULTS=true
```

> **生产环境此选项无效** — 即使设为 `true`，生产环境仍强制要求配置真实密钥。

### `ADMIN_EMAILS`

| 项目 | 说明 |
|------|------|
| **含义** | 管理员邮箱列表（逗号分隔），拥有这些邮箱的用户注册后自动获得管理员角色 |
| **类型** | 字符串（逗号分隔） |
| **默认值** | 空 |

```env
ADMIN_EMAILS=admin@museum.com,curator@museum.com
```

> 生产环境中此配置已弃用，建议使用 `scripts/bootstrap_admin.py` 脚本创建管理员。

### `TRUSTED_PROXIES`

| 项目 | 说明 |
|------|------|
| **含义** | 受信任的代理/负载均衡器 IP 列表（逗号分隔），这些 IP 发送的 `X-Forwarded-For` 头会被信任 |
| **类型** | 字符串（逗号分隔） |
| **默认值** | 空 |

```env
TRUSTED_PROXIES=10.0.0.1,10.0.0.2
```

---

## 数据库

### `DATABASE_URL`

| 项目 | 说明 |
|------|------|
| **含义** | PostgreSQL 异步连接字符串 |
| **类型** | 字符串（URL 格式） |
| **默认值** | `sqlite+aiosqlite:///:memory:`（内存 SQLite，仅测试用） |

格式：`postgresql+asyncpg://用户名:密码@主机:端口/数据库名`

```env
# 本地 PostgreSQL
DATABASE_URL=postgresql+asyncpg://museai:your_password@localhost:5432/museai

# 远程 PostgreSQL
DATABASE_URL=postgresql+asyncpg://museai:your_password@db.example.com:5432/museai

# 测试用内存数据库
DATABASE_URL=sqlite+aiosqlite:///:memory:
```

---

## Elasticsearch

### `ELASTICSEARCH_URL`

| 项目 | 说明 |
|------|------|
| **含义** | Elasticsearch 服务地址 |
| **类型** | 字符串（URL） |
| **默认值** | `http://localhost:9200` |

```env
ELASTICSEARCH_URL=http://localhost:9200
```

### `ELASTICSEARCH_INDEX`

| 项目 | 说明 |
|------|------|
| **含义** | Elasticsearch 索引名称，用于存储文档分块和向量 |
| **类型** | 字符串 |
| **默认值** | `museai_chunks_v1` |

```env
ELASTICSEARCH_INDEX=museai_chunks_v1
```

---

## Redis

### `REDIS_URL`

| 项目 | 说明 |
|------|------|
| **含义** | Redis 连接地址，用于缓存、令牌黑名单等 |
| **类型** | 字符串（URL 格式） |
| **默认值** | `redis://localhost:6379` |

URL 格式支持指定数据库编号：`redis://主机:端口/数据库编号`

```env
# 默认数据库
REDIS_URL=redis://localhost:6379

# 指定数据库 2
REDIS_URL=redis://localhost:6379/2

# 带密码
REDIS_URL=redis://:your_password@localhost:6379
```

---

## LLM 大语言模型

### `LLM_PROVIDER`

| 项目 | 说明 |
|------|------|
| **含义** | LLM 服务提供商 |
| **类型** | 字符串 |
| **默认值** | `openai` |
| **可选值** | 任何 OpenAI 兼容的 provider 名称（`openai`、`deepseek`、`ollama` 等） |

```env
LLM_PROVIDER=openai
```

### `LLM_BASE_URL`

| 项目 | 说明 |
|------|------|
| **含义** | LLM API 基础地址 |
| **类型** | 字符串（URL） |
| **默认值** | `https://api.openai.com/v1` |

```env
# OpenAI 官方
LLM_BASE_URL=https://api.openai.com/v1

# DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1

# 本地 Ollama
LLM_BASE_URL=http://localhost:11434/v1

# 其他 OpenAI 兼容服务
LLM_BASE_URL=https://your-proxy.example.com/v1
```

### `LLM_API_KEY`

| 项目 | 说明 |
|------|------|
| **含义** | LLM API 密钥 |
| **类型** | 字符串 |
| **默认值** | 空（生产环境**必须**设置） |

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

> 当 `ALLOW_INSECURE_DEV_DEFAULTS=true` 且非生产环境时，留空会自动使用不安全的开发默认值。

### `LLM_MODEL`

| 项目 | 说明 |
|------|------|
| **含义** | 使用的 LLM 模型标识符 |
| **类型** | 字符串 |
| **默认值** | `gpt-4o-mini` |

```env
# OpenAI
LLM_MODEL=gpt-4o-mini
LLM_MODEL=gpt-4o

# DeepSeek
LLM_MODEL=deepseek-chat

# 本地 Ollama
LLM_MODEL=qwen2.5:7b
```

### `LLM_HEADERS`

| 项目 | 说明 |
|------|------|
| **含义** | 发送给 LLM API 的额外 HTTP 头（JSON 格式） |
| **类型** | 字符串（JSON） |
| **默认值** | 空 |

```env
LLM_HEADERS={"User-Agent": "curl/8.5.0", "X-Custom-Header": "value"}
```

---

## Embedding 向量模型

### `EMBEDDING_PROVIDER`

| 项目 | 说明 |
|------|------|
| **含义** | Embedding 服务提供商 |
| **类型** | 字符串 |
| **默认值** | `ollama` |
| **可选值** | `ollama` 等 |

```env
EMBEDDING_PROVIDER=ollama
```

### `EMBEDDING_OLLAMA_BASE_URL`

| 项目 | 说明 |
|------|------|
| **含义** | Ollama 服务地址 |
| **类型** | 字符串（URL） |
| **默认值** | `http://localhost:11434` |

```env
EMBEDDING_OLLAMA_BASE_URL=http://localhost:11434
```

### `EMBEDDING_OLLAMA_MODEL`

| 项目 | 说明 |
|------|------|
| **含义** | Ollama Embedding 模型名称 |
| **类型** | 字符串 |
| **默认值** | `nomic-embed-text` |

```env
EMBEDDING_OLLAMA_MODEL=nomic-embed-text
```

### `EMBEDDING_DIMS`

| 项目 | 说明 |
|------|------|
| **含义** | 向量维度，必须与所用 Embedding 模型的输出维度一致 |
| **类型** | 整数 |
| **默认值** | `768` |
| **范围** | 1 ~ 4096 |

常见模型的维度：

| 模型 | 维度 |
|------|------|
| `nomic-embed-text` | 768 |
| `text-embedding-3-small` | 1536 |
| `text-embedding-3-large` | 3072 |
| `bge-m3` | 1024 |

```env
EMBEDDING_DIMS=768
```

> **注意**：修改维度后需要重建 Elasticsearch 索引并重新生成所有文档的向量。

---

## Rerank 重排序

Rerank 对检索结果进行二次排序，提升相关性。配置为可选功能。

### `RERANK_PROVIDER`

| 项目 | 说明 |
|------|------|
| **含义** | Rerank 服务提供商 |
| **类型** | 字符串 |
| **默认值** | `openai` |
| **可选值** | `openai` / `cohere` / `custom` |

留空则禁用 Rerank。

```env
RERANK_PROVIDER=openai
```

### `RERANK_BASE_URL`

| 项目 | 说明 |
|------|------|
| **含义** | Rerank API 地址 |
| **类型** | 字符串（URL） |
| **默认值** | 空 |

```env
RERANK_BASE_URL=https://api.example.com/v1
```

### `RERANK_API_KEY`

| 项目 | 说明 |
|------|------|
| **含义** | Rerank API 密钥 |
| **类型** | 字符串 |
| **默认值** | 空 |
| **要求** | 生产环境中配置了 `RERANK_PROVIDER` 时**必须**设置 |

```env
RERANK_API_KEY=your-rerank-api-key
```

### `RERANK_MODEL`

| 项目 | 说明 |
|------|------|
| **含义** | Rerank 模型标识符 |
| **类型** | 字符串 |
| **默认值** | `rerank-v1` |

```env
RERANK_MODEL=rerank-v1
```

### `RERANK_TOP_N`

| 项目 | 说明 |
|------|------|
| **含义** | Rerank 返回的最大结果数 |
| **类型** | 正整数 |
| **默认值** | `10` |

```env
RERANK_TOP_N=10
```

---

## TTS 语音合成

### `TTS_ENABLED`

| 项目 | 说明 |
|------|------|
| **含义** | 是否启用语音合成功能 |
| **类型** | 布尔值 |
| **默认值** | `False` |
| **可选值** | `true` / `false` |

```env
TTS_ENABLED=true
```

### `TTS_PROVIDER`

| 项目 | 说明 |
|------|------|
| **含义** | TTS 服务提供商 |
| **类型** | 字符串 |
| **默认值** | `xiaomi` |
| **可选值** | `xiaomi` / `mock` |

- `xiaomi` — 小米 MiMo TTS 服务
- `mock` — 模拟 TTS（测试用，不产生真实音频）

```env
TTS_PROVIDER=xiaomi
```

### `TTS_API_KEY`

| 项目 | 说明 |
|------|------|
| **含义** | TTS API 密钥 |
| **类型** | 字符串 |
| **默认值** | 空 |
| **要求** | 生产环境中 `TTS_ENABLED=true` 且 `TTS_PROVIDER` 非 `mock` 时**必须**设置 |

```env
TTS_API_KEY=your-tts-api-key
```

### `TTS_DEFAULT_VOICE`

| 项目 | 说明 |
|------|------|
| **含义** | 默认 TTS 语音/角色名称 |
| **类型** | 字符串 |
| **默认值** | `冰糖` |

```env
TTS_DEFAULT_VOICE=冰糖
```

### `TTS_TIMEOUT`

| 项目 | 说明 |
|------|------|
| **含义** | TTS 请求超时时间（秒） |
| **类型** | 浮点数 |
| **默认值** | `30.0` |

```env
TTS_TIMEOUT=30.0
```

---

## 检索与过滤

以下配置控制 RAG 检索管道中的动态文档过滤行为。

### `RETRIEVAL_TOP_K`

| 项目 | 说明 |
|------|------|
| **含义** | 初始检索阶段返回的候选文档数量 |
| **类型** | 正整数 |
| **默认值** | `15` |

```env
RETRIEVAL_TOP_K=15
```

### `RERANK_ABSOLUTE_THRESHOLD`

| 项目 | 说明 |
|------|------|
| **含义** | 绝对分数阈值 — Rerank 分数低于此值的文档会被过滤掉 |
| **类型** | 浮点数 |
| **默认值** | `0.25` |
| **范围** | 0.0 ~ 1.0 |

```env
RERANK_ABSOLUTE_THRESHOLD=0.25
```

### `RERANK_RELATIVE_GAP`

| 项目 | 说明 |
|------|------|
| **含义** | 相对间隔阈值 — 与最高分文档的分差超过此比例的文档会被过滤 |
| **类型** | 浮点数 |
| **默认值** | `0.25` |
| **范围** | 0.0 ~ 1.0 |

例如设置为 `0.25` 时，如果最高分是 `0.8`，则低于 `0.6`（= 0.8 × 0.75）的文档会被过滤。

```env
RERANK_RELATIVE_GAP=0.25
```

### `RERANK_MIN_DOCS`

| 项目 | 说明 |
|------|------|
| **含义** | 过滤后至少保留的文档数量（即使分数很低也保留） |
| **类型** | 正整数 |
| **默认值** | `1` |

```env
RERANK_MIN_DOCS=1
```

### `RERANK_MAX_DOCS`

| 项目 | 说明 |
|------|------|
| **含义** | 过滤后最多保留的文档数量 |
| **类型** | 正整数 |
| **默认值** | `8` |

```env
RERANK_MAX_DOCS=8
```

---

## 分块合并

控制检索结果中父子分块的合并策略。

### `CHUNK_MERGE_ENABLED`

| 项目 | 说明 |
|------|------|
| **含义** | 是否启用分块合并（将子分块提升为父分块以提供更完整的上下文） |
| **类型** | 布尔值 |
| **默认值** | `True` |
| **可选值** | `true` / `false` |

```env
CHUNK_MERGE_ENABLED=true
```

### `CHUNK_MERGE_MAX_LEVEL`

| 项目 | 说明 |
|------|------|
| **含义** | 合并时向上追溯的最大层级数 |
| **类型** | 整数 |
| **默认值** | `1` |

```env
CHUNK_MERGE_MAX_LEVEL=1
```

### `CHUNK_MERGE_MAX_PARENTS`

| 项目 | 说明 |
|------|------|
| **含义** | 单次合并操作最多提升的父分块数量 |
| **类型** | 整数 |
| **默认值** | `3` |

```env
CHUNK_MERGE_MAX_PARENTS=3
```

---

## CORS 跨域

### `CORS_ORIGINS`

| 项目 | 说明 |
|------|------|
| **含义** | 允许的跨域来源（逗号分隔的 URL 列表，或 `"*"` 允许所有来源） |
| **类型** | 字符串（逗号分隔） |
| **默认值** | `http://localhost:3000` |

```env
# 单个来源
CORS_ORIGINS=http://localhost:3000

# 多个来源
CORS_ORIGINS=http://localhost:3000,https://museum.example.com

# 开发环境允许所有来源
CORS_ORIGINS=*
```

> **生产环境禁止使用 `"*"`**，必须明确列出允许的来源。

### `CORS_ALLOW_CREDENTIALS`

| 项目 | 说明 |
|------|------|
| **含义** | 是否允许携带凭证（Cookie、Authorization 头）的跨域请求 |
| **类型** | 布尔值 |
| **默认值** | `True` |
| **可选值** | `true` / `false` |

```env
CORS_ALLOW_CREDENTIALS=true
```

---

## 日志

### `LOG_LEVEL`

| 项目 | 说明 |
|------|------|
| **含义** | 日志输出级别 |
| **类型** | 字符串（枚举，不区分大小写） |
| **默认值** | `INFO` |
| **可选值** | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |

从左到右详细程度递减：

- `DEBUG` — 最详细，包含所有调试信息
- `INFO` — 常规运行信息（推荐生产环境）
- `WARNING` — 警告信息
- `ERROR` — 仅错误
- `CRITICAL` — 仅严重错误

```env
LOG_LEVEL=INFO
```

### `LOG_DIR`

| 项目 | 说明 |
|------|------|
| **含义** | 日志文件输出目录 |
| **类型** | 字符串（路径） |
| **默认值** | `logs` |

```env
LOG_DIR=logs
```

### `LOG_FORMAT`

| 项目 | 说明 |
|------|------|
| **含义** | 日志输出格式 |
| **类型** | 字符串 |
| **默认值** | `json` |
| **可选值** | `json` / `text` |

- `json` — 结构化 JSON 格式，适合日志收集系统（如 ELK）
- `text` — 纯文本格式，适合本地开发阅读

```env
LOG_FORMAT=json
```

---

## 速率限制

### `RATE_LIMIT_ENABLED`

| 项目 | 说明 |
|------|------|
| **含义** | 是否启用 API 速率限制 |
| **类型** | 布尔值 |
| **默认值** | `True` |
| **可选值** | `true` / `false` |

禁用速率限制适用于负载测试等场景。注意：认证端点的速率限制采用 fail-closed 策略（Redis 不可用时拒绝请求），普通端点采用 fail-open 策略（Redis 不可用时放行）。

```env
RATE_LIMIT_ENABLED=true
```

---

## 生产环境检查清单

生产部署时，以下配置**必须**正确设置，否则应用将拒绝启动：

| 配置项 | 要求 |
|--------|------|
| `JWT_SECRET` | 必须设置，长度 ≥ 32 字符 |
| `LLM_API_KEY` | 必须设置 |
| `RERANK_API_KEY` | 当 `RERANK_PROVIDER` 已设置时必须 |
| `TTS_API_KEY` | 当 `TTS_ENABLED=true` 且 `TTS_PROVIDER` 非 `mock` 时必须 |
| `CORS_ORIGINS` | 不能为 `"*"` |
| `APP_ENV` | 应设为 `production` |
| `ALLOW_INSECURE_DEV_DEFAULTS` | 应设为 `false`（或不设置） |
