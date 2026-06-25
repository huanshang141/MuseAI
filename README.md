# MuseAI 后端

English version: [README_EN.md](./README_EN.md)

MuseAI 后端是面向西安半坡博物馆微信小程序的 FastAPI 服务，负责导览会话、SSE 流式回答、展厅与展品数据、AI 策展路线、游览报告、Reflection Engine、RAG 检索、LLM 调用以及 TTS 语音合成。

## 当前阶段

当前处于 **上线准备与发布收口阶段**。后端已经支撑小程序的核心体验闭环，预想中的小程序功能已完成真机测试；ICP备案和微信 request 合法域名链路已通过，正式上线仍受真实数据、OCR 服务、API key 治理、运维托管和体验版发布流程影响。完整执行手册见 [上线准备.md](../project_materials/docs/上线准备.md)。

## 已实现能力

- 游客导览 session 与 `X-Session-Token`。
- `/api/v1/tour/sessions/{id}/chat/stream` SSE 流式导览回答。
- 四类导览身份：
  - `A` 考古研究员
  - `B` 研学记录员
  - `C` 历史追问者
  - `D` 器物研究员
- 三步问卷上下文注入：追问方向、初始判断、导览节奏。
- 展厅 slug 规范化和中文名映射；当前只接受展厅信息导入的 9 个 canonical hall slug。
- 展厅进入、展厅离开、展品浏览、提问、AI 回答、深挖等事件记录。
- `/api/v1/curator/plan-tour` AI 策展路线接口。
- 展品列表、展品详情、按展厅筛选和文字搜索。
- 游览报告生成：到访展厅、展品浏览、认知变化、记录摘要、基础统计。
  - 到访展厅按已浏览展厅统计：`exhibit_question` 或 `exhibit_view` 会计入，`assistant_answer` 作为历史兼容事件保留。
  - 问题统计按用户发送消息数统计：`exhibit_question` 每条计一次，不对相同文本去重。
  - 展品浏览单独统计：点进展品详情页记录 `exhibit_view`，同一展品重复查看只计一次。
  - 记录摘要按展厅聚合用户问题与 AI 回答，优先使用报告模型生成凝练摘要，失败时回退规则式摘要。
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

## 尚未完成或仍需发布验收

HTTPS 状态拆分说明：

- 已完成：`banpo-museai.xyz` ICP 备案已通过；`api.banpo-museai.xyz` DNS、SSL 证书、Nginx 443 反代已配置，`https://api.banpo-museai.xyz/api/v1/health` 已返回 healthy。
- 当前开发状态：小程序前端已切到 `https://api.banpo-museai.xyz/api/v1` 进行测试；公网 HTTP 调试入口仅保留为紧急 fallback 或历史排查用途。
- 已完成（微信侧）：微信公众平台 request 合法域名已配置，刷新开发者工具域名信息后，关闭合法域名豁免已通过真机测试。

其余事项：

- OCR 服务尚未购买或配置；OCR 识别当前主要在小程序端调用微信能力并回退到展品文字匹配，后端未新增 OCR API。
- 官方馆方完整展品清单、展品图片、地图、点位和空间布局数据仍需确认；当前数据不是最终真实数据。
- LLM Qwen API 由 Alex 提供，其他 API 由另一位同学提供；上线前必须明确 key 负责人、额度、付费、告警和轮换流程。
- 当前 Qwen 调用消耗免费额度或试用额度；体验版前必须在服务商控制台确认额度、限流和账单策略。
- 生产级进程管理（systemd）、日志轮转和数据库备份策略已有部署资产（见 `deploy/`），但尚未在服务器落地执行。
- 体验版上传、测试成员分发和上传前完整回归尚未完成。

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

## 报告与事件契约

报告统计依赖 `tour_events`，前端上报事件必须使用 9 个 canonical hall slug 或对应中文展厅名。后端不再保留历史 slug 兼容映射，无法归一到 9 个展厅的 hall 值会被丢弃。

目前会计入到访展厅的事件类型：

- `exhibit_question`
- `exhibit_view`
- `assistant_answer`

这意味着用户只是进入展厅不会被计入 `halls_visited`；在展厅内发送消息，或点进该厅任意展品详情页，都会计入对应展厅。`halls_visited` 按 canonical hall slug 去重。问题数由 `exhibit_question` 计数，每条用户发送消息计一次，不对相同问题文本去重。展品浏览由 `exhibit_view` 单独计入展品统计，并按展品去重。

`POST /api/v1/tour/sessions/{session_id}/events` 的 `metadata` 会持久化到事件的 JSON 字段，报告会从其中提取问题、AI 回答、展品和展厅信息。不要把隐私数据、完整 API key 或用户敏感信息放入 `metadata`。

`POST /api/v1/tour/sessions/{session_id}/report` 当前重点返回：

- `halls_visited`：已归一化的到访展厅 slug 列表。
- `highlights`：本次导览亮点。
- `reflection`：Reflection Engine 规则推断出的认知变化。
- `record_notes`：按展厅合并用户问题和 AI 回答后的记录摘要，供前端直接渲染。

报告生成不新增数据库表、不新增 API，也不改变 SSE 协议。`record_notes` 会优先调用报告模型生成不超过约 300 字的凝练记录摘要；模型不可用或生成失败时回退到规则式摘要，避免报告不可用。

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

API key 分工建议：

- `LLM_API_KEY` 当前由 Alex 维护，主要用于 Qwen/DashScope 导览对话和报告摘要。
- `RERANK_API_KEY`、`TTS_API_KEY`、未来 OCR 或其他服务 key 由对应同学维护。
- 仓库只记录配置项名称，不记录真实 key。
- 免费额度不能视为长期生产方案；体验版前必须确认是否转为付费、是否有账单告警、是否有备用 model id。
- 替换供应商时优先通过 `.env` 切换 OpenAI-compatible provider，不在上线窗口大改 RAG 或 SSE 协议。

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
py -3 -m py_compile backend/app/application/tour_event_service.py
uv run --extra dev pytest backend/tests/unit/test_tour_chat.py -q
uv run --extra dev pytest backend/tests/unit/test_tour_services.py -q
uv run --extra dev pytest backend/tests/unit/test_tts_core.py backend/tests/unit/test_tts_advanced.py backend/tests/unit/test_voice_description_helpers.py -q
uv run --extra dev pytest backend/tests/contract/test_tour_api.py -q
```

全量测试：

```bash
uv run --extra dev pytest -q
# Windows 临时目录被旧句柄锁住时，可使用隔离目录：
uv run --extra dev pytest -q --basetemp .pytest-tmp
```

## 服务器部署要点

当前服务器资源口径已调整为 **2 核 / 8 GB RAM**，部署与性能调优按这个预算处理。当前服务器曾采用以下形态：

- Uvicorn 监听 `127.0.0.1:8000`。
- Nginx 反向代理到后端。
- 小程序当前应使用 `https://api.banpo-museai.xyz/api/v1` 测试；如临时回退到 `http://122.152.232.190:3000/api/v1`，正式上传前必须切回 HTTPS 并关闭微信开发者工具合法域名豁免。
- 历史说明：早期开发调试曾使用 `http://122.152.232.190:3000/api/v1`，HTTPS 真机验证通过后应在服务器侧关闭该公网 HTTP 入口（见 `deploy/DEPLOYMENT_NOTES.md`）。

2 核 / 8 GB 下的建议：

- 后端优先保持单个 Uvicorn worker，避免 Redis、Elasticsearch、PostgreSQL 与 Python 进程争抢内存。
- RAG、rerank、TTS 均依赖外部服务，线上应控制并发和超时，优先保证小程序导览流式响应。
- Elasticsearch、Redis、PostgreSQL 如与后端同机部署，需要持续观察内存占用；数据量增长后优先拆分检索或数据库服务。

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

上线前建议改为 systemd 或 Docker Compose 托管，不再依赖手动 `nohup`。systemd unit、logrotate 规则和 PostgreSQL 备份脚本已提供在 `deploy/` 目录，部署步骤见 `deploy/DEPLOYMENT_NOTES.md`。

## 上线前阻断项

- 微信公众平台 request 合法域名已配置并通过关闭豁免后的真机测试；如后续使用上传/下载文件 URL，再确认 uploadFile/downloadFile 合法域名。
- 前端 API 已从开发 IP 切到 HTTPS 域名。
- 真实馆方展品、展厅、图片和空间数据已导入并抽样核验。
- OCR 上线策略已确定：购买并配置服务 ID，或隐藏 OCR 入口只保留文字搜索。
- Qwen/DashScope 免费额度、付费开通、限流和账单告警已确认。
- API key 负责人和轮换流程已明确。
- 重置曾暴露过的 AppSecret 和 API key。
- 配置 systemd/Docker Compose、日志轮转、数据库备份和回滚流程。
- 完成 iOS/Android 真机全链路测试：问卷、路线、导览、TTS、OCR、报告。

## 安全注意

- 不提交 `.env`、`.env.backup*`、私钥、AppSecret、LLM key、TTS key。
- 证书私钥只保留在线上服务器安全目录，权限建议 `600`。
- 调试日志中不要输出完整 API key、AppSecret、用户 token 或原始隐私数据。
