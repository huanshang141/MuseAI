# MuseAI 后端

MuseAI 后端是面向半坡博物馆微信小程序的 FastAPI 服务，负责导览会话、SSE 流式 AI 回答、展品浏览、游览报告、策展路线接口、后台内容管理、RAG 检索、LLM 调用追踪和可选 TTS。

当前产品阶段：Stage 10C。微信小程序是首要交付形态，生产服务器目标规格为腾讯云 2 核 4G，因此后端设计和优化应避免不必要的模型调用、重型后台任务和额外常驻服务。

## 当前状态

已实现并仍在使用：

- 微信小程序游客导览流程。
- 游客导览 session 和 `X-Session-Token`。
- `/api/v1/tour/sessions/{id}/chat/stream` SSE 流式导览回答。
- 导览事件、真实到访展厅统计、报告生成。
- 四类导览身份：
  - `A` 考古研究员
  - `B` 研学记录员
  - `C` 历史追问者
  - `D` 器物研究员
- 半坡展厅 slug 规范化和旧 slug 兼容。
- 公共展品浏览、按展厅筛选和搜索。
- 后台展品、展厅、文档、Prompt、LLM trace、TTS persona 管理 API。
- RAG 链路：query rewrite、Elasticsearch 检索、rerank、文档过滤、流式生成。
- DeepSeek thinking 默认关闭：`LLM_ENABLE_THINKING=false`。
- LLM 模型分层：
  - `LLM_TOUR_MODEL=deepseek-v4-flash` 用于普通导览和 RAG 流式回答。
  - `LLM_REPORT_MODEL=deepseek-v4-pro` 用于报告摘要。
  - `LLM_MODEL` 保留为兼容兜底字段。
- 展品列表和搜索接口已改为轻量 count 统计。
- Redis 或 Elasticsearch 不可用时进入 degraded 模式，而不是整站直接不可用。

保留但当前小程序端不重点使用：

- `/api/v1/curator/plan-tour` 结构化路线接口。
- 通用 chat API。
- 文档上传和摄入 API。
- TTS 合成 API。

尚未生产闭环：

- 拍照识别展品。
- 语音输入。
- 小程序端 TTS 播放闭环。
- 官方博物馆地图和展厅点位数据。
- 馆方授权的完整展品清单、图片和空间位置。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| API | FastAPI, Pydantic v2 |
| 运行时 | Python 3.11+, uv, Uvicorn |
| 数据库 | PostgreSQL 16, SQLAlchemy async |
| 缓存 | Redis 7 |
| 检索 | Elasticsearch 8, 自定义 IK analyzer 镜像 |
| RAG | LangChain, LangGraph, 自定义 retriever/filter |
| LLM | OpenAI-compatible provider，当前按 DeepSeek 兼容接口配置 |
| Rerank | SiliconFlow/OpenAI/Cohere/custom/mock |
| TTS | Xiaomi MiMo 或 mock provider，可选 |
| 测试 | pytest, pytest-asyncio |

## 目录结构

```text
backend/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routers
│   │   │   ├── admin/              # 后台内容、Prompt、trace、TTS API
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── curator.py
│   │   │   ├── documents.py
│   │   │   ├── exhibits.py
│   │   │   ├── health.py
│   │   │   ├── profile.py
│   │   │   ├── tour.py
│   │   │   └── tts.py
│   │   ├── application/            # 应用服务和用例层
│   │   ├── config/                 # settings 与环境变量校验
│   │   ├── domain/                 # 领域实体和异常
│   │   ├── infra/                  # PostgreSQL、Redis、ES、provider、LangChain
│   │   ├── observability/          # 日志和请求中间件
│   │   └── main.py                 # FastAPI 入口
│   ├── alembic/                    # 数据库迁移
│   └── tests/                      # unit、contract、e2e 测试
├── deploy/
│   └── nginx.conf                  # HTTPS/SSE 反向代理模板
├── docker/
│   └── elasticsearch/              # Elasticsearch 自定义镜像
├── docs/
│   ├── reference/展品.md            # 半坡展品导入来源
│   └── *.md                        # 审计、性能诊断和交接文档
├── scripts/
│   ├── init_db.py
│   ├── seed_prompts_and_personas.py
│   ├── import_real_exhibits_via_api.py
│   └── ...
├── .env.example
├── CONFIGURATION.md
├── docker-compose.yml              # 目前只启动 PostgreSQL、Redis、Elasticsearch
├── pyproject.toml
└── uv.lock
```

## API 概览

所有应用接口都挂载在 `/api/v1` 下。

| 模块 | 端点示例 | 用途 |
| --- | --- | --- |
| 健康检查 | `GET /health`, `GET /ready` | 服务和依赖状态 |
| 认证 | `POST /auth/register`, `POST /auth/login` | 用户和管理员认证 |
| 导览 | `POST /tour/sessions`, `POST /tour/sessions/{id}/chat/stream` | 小程序导览 session 与 SSE 回答 |
| 报告 | `POST /tour/sessions/{id}/report`, `GET /tour/sessions/{id}/report` | 生成或读取游览报告 |
| 展品 | `GET /exhibits`, `GET /exhibits/{id}` | 公共展品浏览与搜索 |
| 策展 | `POST /curator/plan-tour`, `/narrative`, `/reflection` | 结构化路线、叙事和反思问题 |
| TTS | `POST /tts/synthesize` | 可选语音合成 |
| 后台 | `/admin/exhibits`, `/admin/halls`, `/admin/prompts`, `/admin/documents`, `/admin/llm-traces`, `/admin/tts/personas` | 内容与运维管理 |

## 配置说明

运行配置由 `backend/app/config/settings.py` 从 `backend/.env` 读取。真实 `.env` 不允许提交仓库。

关键字段：

| 字段 | 当前含义 |
| --- | --- |
| `APP_ENV` | `development`、`test`、`local` 或 `production` |
| `DEBUG` | 生产环境保持 `false` |
| `ALLOW_INSECURE_DEV_DEFAULTS` | 仅本地调试可用，生产必须 `false` |
| `DATABASE_URL` | PostgreSQL async 连接串 |
| `REDIS_URL` | Redis 连接串 |
| `ELASTICSEARCH_URL` | Elasticsearch 地址 |
| `JWT_SECRET` | 生产环境必填，至少 32 字符 |
| `LLM_BASE_URL` | OpenAI-compatible LLM base URL |
| `LLM_API_KEY` | 生产环境必填 |
| `LLM_MODEL` | 兼容兜底模型 |
| `LLM_TOUR_MODEL` | 导览、RAG、流式回答默认模型 |
| `LLM_REPORT_MODEL` | 报告摘要模型 |
| `LLM_ENABLE_THINKING` | `false` 时向支持的模型发送 thinking disabled |
| `LLM_HEADERS` | 可选 JSON 字符串，用于额外上游请求头 |
| `RERANK_PROVIDER` | `siliconflow`、`openai`、`cohere`、`custom` 或 `mock` |
| `TTS_ENABLED` | 语音功能未闭环前建议保持 `false` |
| `CORS_ORIGINS` | 生产环境不能使用通配符 |
| `TRUSTED_PROXIES` | 仅填写可信反代 IP，例如本机 Nginx 后面填 `127.0.0.1` |

更完整的操作流程见根目录 `后端配置文档.md`。

## 本地运行

```bash
cd backend

# 1. 创建本地配置
cp .env.example .env

# 2. 安装依赖
uv sync

# 3. 启动基础设施
docker compose up -d

# 4. 初始化数据库和 ES index
uv run python scripts/init_db.py --init-es

# 5. 同步 prompts、personas 和 halls
uv run python scripts/seed_prompts_and_personas.py

# 6. 启动开发服务
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/ready
```

## 数据导入

当前半坡展品导入路径：

```bash
cd backend
uv run python scripts/import_real_exhibits_via_api.py \
  --base-url http://127.0.0.1:8000/api/v1 \
  --email <admin-email> \
  --password '<admin-password>'
```

注意：该脚本会清理已有展品、文档和展厅，再从 `docs/reference/展品.md` 导入。只有确认要重置展品数据时再运行。

## 测试

常用检查：

```bash
cd backend

py -3 -m compileall -q backend scripts backend/tests
uv run --extra dev pytest -q
```

聚焦测试：

```bash
uv run --extra dev pytest backend/tests/contract/test_tour_api.py -q
uv run --extra dev pytest backend/tests/contract/test_exhibits_api.py -q
uv run --extra dev pytest backend/tests/unit/test_tour_chat.py -q
uv run --extra dev pytest backend/tests/unit/test_llm_provider.py backend/tests/unit/test_config.py -q
```

近期变更总结中记录的完整基线：

```text
996 passed, 23 skipped, 12 warnings
```

如果 Windows 本地 pytest 遇到临时目录权限问题，可先把 `TMP` 和 `TEMP` 指向项目内临时目录再运行。

## 生产部署说明

当前 `docker-compose.yml` 只启动 PostgreSQL、Redis、Elasticsearch，不包含 FastAPI API 服务。当前 2 核 4G 服务器推荐部署形态：

1. 用 `docker compose up -d` 启动基础设施。
2. 执行迁移和 seed 脚本。
3. 用 `systemd` 托管：
   ```bash
   uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```
4. 用宝塔或 Nginx 将 HTTPS 域名的 `/api/` 反向代理到 `127.0.0.1:8000`。
5. 不对公网暴露 PostgreSQL、Redis、Elasticsearch 和 8000 端口。
6. 在微信公众平台把 HTTPS API 域名配置为小程序 request 合法域名。

SSE 流式回答需要反代关闭 buffering，并设置较长的 read timeout。

## 运维约定

- 永远不要提交 `backend/.env`。
- 后端配置变化时必须同步更新 `.env.example`、`settings.py`、`CONFIGURATION.md`、`README.md`、`README_CN.md` 和根目录 `后端配置文档.md`。
- 普通导览默认使用 `LLM_TOUR_MODEL`，报告和研究型摘要使用 `LLM_REPORT_MODEL`。
- 不要把 tour chat 的重复 LLM 调用重新引入。
- 新增后端能力前先评估 2 核 4G 生产服务器是否能承受。
- 拍照/OCR/语音功能未完成前，前端应隐藏或明确标记为未开放，避免影响小程序审核和用户体验。
