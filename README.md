# MuseAI 后端

English version: [README_EN.md](./README_EN.md)

MuseAI 后端是面向西安半坡博物馆微信小程序的 FastAPI 服务，负责导览会话、SSE 流式回答、展厅与展品数据、AI 策展路线、游览报告、Reflection Engine、RAG 检索、LLM 调用以及 TTS 语音合成。

## 当前阶段

当前处于 **Stage 13 上线前闭环验证与发布准备**。后端已经支撑小程序的核心体验闭环，但正式上线仍受备案、微信合法域名、真机测试和运维托管流程影响。

## 已实现能力

- 游客导览 session 与 `X-Session-Token`。
- `/api/v1/tour/sessions/{id}/chat/stream` SSE 流式导览回答。
- 四类导览身份：
  - `A` 考古研究员
  - `B` 研学记录员
  - `C` 历史追问者
  - `D` 器物研究员
- 三步问卷上下文注入：追问方向、初始判断、导览节奏。
- 展厅 slug 规范化、中文名映射和历史 slug 兼容。
- 展厅进入、展品浏览、提问、深挖等事件记录。
- `/api/v1/curator/plan-tour` AI 策展路线接口。
- 展品列表、展品详情、按展厅筛选和文字搜索。
- 游览报告生成：到访展厅、认知变化、记录摘要、基础统计。
- Reflection Engine：不新增数据库、不新增 API、不新增模型调用，基于 session/events/report 规则推断认知变化。
- RAG 链路：query rewrite、Elasticsearch 检索、rerank、文档过滤、流式生成。
- LLM 分层模型：
  - `LLM_TOUR_MODEL` 用于普通导览对话。
  - `LLM_REPORT_MODEL` 用于报告等总结任务。
  - `LLM_MODEL` 保留为兼容兜底。
- DeepSeek/Qwen OpenAI-compatible 调用兼容：
  - DeepSeek 可关闭 thinking。
  - Qwen/DashScope 可关闭 thinking。
- 导览对话传递结构化 `conversation_history`，改善连续追问相关性。
- Redis 或 Elasticsearch 不可用时进入 degraded 模式，避免直接阻断服务启动。
- `/api/v1/tts/synthesize` TTS 合成接口，当前默认只保留“冰糖”声线，返回可供小程序播放的音频数据。

## 尚未完成或仍需真机验证

- 微信正式小程序备案和 request 合法域名配置。
- `api.banpo-museai.xyz` 已配置 DNS/SSL 和 Nginx，但未备案前在微信真机环境可能不可用。
- OCR 识别当前主要在小程序端调用微信能力并回退到展品文字匹配，后端未新增 OCR API。
- 官方馆方完整展品清单、展品图片、地图、点位和空间布局数据仍需确认。
- 生产级进程管理、日志轮转和数据库备份策略仍需固化。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| API | FastAPI, Pydantic v2 |
| 运行 | Python 3.11+, uv, Uvicorn |
| 数据库 | PostgreSQL / SQLAlchemy async |
| 缓存 | Redis |
| 检索 | Elasticsearch |
| RAG | LangChain, LangGraph, 自定义 retriever/filter |
| LLM | OpenAI-compatible provider |
| Rerank | SiliconFlow / OpenAI / Cohere / custom / mock |
| TTS | Xiaomi MiMo 或 mock provider |
| 测试 | pytest, pytest-asyncio |

## 目录结构

```text
backend/
├── backend/app/
│   ├── api/                 # FastAPI routers
│   ├── application/         # 应用服务与业务编排
│   ├── config/              # settings 与环境变量校验
│   ├── domain/              # 领域异常与实体
│   ├── infra/               # LLM/RAG/数据库/外部服务适配
│   ├── observability/       # 日志与追踪上下文
│   └── main.py              # FastAPI app 入口
├── backend/tests/
├── scripts/
├── docs/
├── docker/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── README.md
└── README_EN.md
```

## 关键 API

| 功能 | 方法与路径 |
| --- | --- |
| 健康检查 | `GET /api/v1/health` |
| 创建导览会话 | `POST /api/v1/tour/sessions` |
| 更新导览会话 | `PATCH /api/v1/tour/sessions/{session_id}` |
| 流式导览回答 | `POST /api/v1/tour/sessions/{session_id}/chat/stream` |
| 上报导览事件 | `POST /api/v1/tour/sessions/{session_id}/events` |
| 生成游览报告 | `POST /api/v1/tour/sessions/{session_id}/report` |
| 策展路线 | `POST /api/v1/curator/plan-tour` |
| 展品列表 | `GET /api/v1/exhibits` |
| 展品详情 | `GET /api/v1/exhibits/{id}` |
| TTS 合成 | `POST /api/v1/tts/synthesize` |

## 环境变量

复制示例配置：

```bash
cp .env.example .env
```

关键配置：

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379/0
ELASTICSEARCH_URL=http://localhost:9200
JWT_SECRET=

LLM_PROVIDER=qwen
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=
LLM_MODEL=qwen-flash
LLM_TOUR_MODEL=qwen-flash
LLM_REPORT_MODEL=qwen-plus
LLM_HEADERS=
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=800
LLM_ENABLE_THINKING=false
LLM_COMPAT_MODE=qwen

RERANK_PROVIDER=siliconflow
RERANK_API_KEY=
RERANK_MODEL=BAAI/bge-reranker-v2-m3

TTS_PROVIDER=xiaomi
TTS_API_KEY=
TTS_MODEL=mimo-v2.5-tts
TTS_DEFAULT_VOICE=冰糖
```

`.env` 不允许提交到仓库。线上修改 `.env` 后必须重启后端进程。

## 本地运行

```bash
cd backend
uv sync --extra dev
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## 测试

常用检查：

```bash
cd backend
py -3 -m py_compile backend/app/api/tour.py backend/app/api/curator.py backend/app/api/tts.py backend/app/application/tour_chat_service.py backend/app/application/tour_report_service.py
uv run --extra dev pytest backend/tests/unit/test_tour_chat.py -q
uv run --extra dev pytest backend/tests/unit/test_tts_core.py backend/tests/unit/test_tts_advanced.py backend/tests/unit/test_voice_description_helpers.py -q
uv run --extra dev pytest backend/tests/contract/test_tour_api.py -q
```

全量测试：

```bash
uv run --extra dev pytest -q
```

## 服务器部署要点

当前服务器曾采用以下形态：

- Uvicorn 监听 `127.0.0.1:8000`。
- Nginx 反向代理到后端。
- 开发调试可通过 `http://122.152.232.190:3000/api/v1`。
- 正式小程序应使用 `https://api.banpo-museai.xyz/api/v1`，但域名备案和微信后台合法域名通过前不能作为正式真机入口。

服务器更新代码后通常需要：

```bash
cd ~/MuseAI
git pull myfork main
pkill -f "uv run uvicorn backend.app.main:app" || true
nohup uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > backend_uvicorn.log 2>&1 &
sleep 3
curl -i http://127.0.0.1:8000/api/v1/health
curl -i https://api.banpo-museai.xyz/api/v1/health
```

上线前建议改为 systemd 或 Docker Compose 托管，不再依赖手动 `nohup`。

## 上线前阻断项

- 明确小程序备案主体：个人、学校/项目依托单位或博物馆合作主体。
- 备案通过后，在微信公众平台配置 request/uploadFile/downloadFile 合法域名。
- 将前端 API 从开发 IP 切到 HTTPS 域名。
- 重置曾暴露过的 AppSecret 和 API key。
- 配置 systemd/Docker Compose、日志轮转、数据库备份和回滚流程。
- 完成 iOS/Android 真机全链路测试：问卷、路线、导览、TTS、OCR、报告。

## 安全注意

- 不提交 `.env`、`.env.backup*`、私钥、AppSecret、LLM key、TTS key。
- 证书私钥只保留在线上服务器安全目录，权限建议 `600`。
- 调试日志中不要输出完整 API key、AppSecret、用户 token 或原始隐私数据。
