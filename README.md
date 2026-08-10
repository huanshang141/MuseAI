# MuseAI 后端

English version: [README_EN.md](./README_EN.md)

MuseAI 后端是面向西安半坡博物馆微信小程序的 FastAPI 服务，负责导览会话、SSE 流式回答、展厅与展品数据、AI 策展路线、游览报告、Reflection Engine、RAG 检索、LLM 调用以及 TTS 语音合成。

## 当前阶段

当前处于 **数据驱动小程序框架验证阶段**。九个展厅的名称和简介为已确认内容；当前展品、图片和地图/路线仍是测试数据或待接入项。后端已提供统一 CSV/XLSX 导入、具体建议条、报告探索指引和展品图片管理能力；部署、实机回归和真实馆方数据验收仍需按发布批次执行。数据与图片维护见 [小程序内容维护指南](./docs/miniapp-content-maintenance.md)。

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
- 数据驱动建议条：CSV/XLSX 中显式提供的问题必须全部通过质量校验，任一无效值都会使整批 dry-run/import 失败；字段留空时才由展品名称、简介和分类确定性生成可观察的问题，不新增 LLM 调用。
- 展品图片：CSV/XLSX 可提供 HTTPS `image_url`；管理员可上传、替换或删除 JPEG/PNG/WebP；无图时 API 返回 `null`，由小程序显示默认图。
- 游览报告生成：到访展厅、展品浏览、认知变化、记录摘要、基础统计。
  - 到访展厅按有效用户提问或展品浏览统计：非澄清 `exhibit_question` 或 `exhibit_view` 会计入，确定性澄清轮次不计入。
  - `halls_visited` 仅保留为后端内部统计和兼容字段；游客报告不显示到访展厅明细、数量或对应 highlight。
  - 问题统计按用户发送消息数统计：`exhibit_question` 每条计一次，不对相同文本去重。
  - 展品浏览单独统计：点进展品详情页记录 `exhibit_view`，同一展品重复查看只计一次。
  - 记录摘要按展厅聚合用户问题与 AI 回答，优先使用报告模型生成凝练摘要，失败时回退规则式摘要。
  - `exploration_guidance` 以一条明确的 `next_step` 为主，并保留 1 条兼容 `action`；根据最新提问、展品浏览和当前展厅给出下一步，不再因互动较少而返回拒绝型文案。
- Reflection Engine：不新增数据库、不新增 API、不新增模型调用，基于 session/events/report 规则推断认知变化。
- RAG 链路：query rewrite、Elasticsearch 检索、rerank、文档过滤、流式生成。
- LLM 分层模型：
  - `LLM_TOUR_MODEL` 用于普通导览对话。
  - `LLM_REPORT_MODEL` 用于报告等总结任务。
  - `LLM_MODEL` 保留为兼容兜底。
- DeepSeek/Qwen OpenAI-compatible 调用兼容：
  - DeepSeek 可关闭 thinking。
  - Qwen/DashScope 可关闭 thinking。
- 导览对话由服务端按展厅持久化可信历史并压缩用于连续追问；客户端恢复历史只负责界面显示，不进入模型 prompt 或检索改写。
- Redis 或 Elasticsearch 不可用时进入 degraded 模式，避免直接阻断服务启动。
- `/api/v1/tts/synthesize` TTS 合成接口，当前默认只保留“冰糖”声线，返回可供小程序播放的音频数据。

## 尚未完成或仍需发布验收

HTTPS 状态拆分说明：

- 已完成：`banpo-museai.xyz` ICP 备案已通过；`api.banpo-museai.xyz` DNS、SSL 证书、Nginx 443 反代已配置，`https://api.banpo-museai.xyz/api/v1/health` 已返回 healthy。
- 当前开发状态：小程序前端统一使用 `https://api.banpo-museai.xyz/api/v1`；旧公网 HTTP 调试入口已经停用，不再作为 fallback 或排查路径。
- 已完成（微信侧）：微信公众平台 request 合法域名已配置，刷新开发者工具域名信息后，关闭合法域名豁免已通过真机测试。

其余事项：

- OCR 服务尚未购买或配置；OCR 识别当前主要在小程序端调用微信能力并回退到展品文字匹配，后端未新增 OCR API。
- 官方馆方完整展品清单、展品图片、地图、点位和空间布局数据仍需确认；当前数据不是最终真实数据。
- LLM Qwen API 由 Alex 提供，其他 API 由另一位同学提供；上线前必须明确 key 负责人、额度、付费、告警和轮换流程。
- 当前 Qwen 调用消耗免费额度或试用额度；体验版前必须在服务商控制台确认额度、限流和账单策略。
- 生产后端已由 systemd 托管；应用日志由 Loguru 每日轮转并保留 7 天，PostgreSQL 备份 service/timer 位于 `deploy/`，发布批次仍需记录实际备份、校验和恢复演练结果。
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
| 展品公开图片 | `GET /api/v1/exhibits/{id}/image` |
| 管理员上传/删除图片 | `POST` / `DELETE /api/v1/admin/exhibits/{id}/image` |
| TTS 合成 | `POST /api/v1/tts/synthesize` |

## 报告与事件契约

报告统计依赖 `tour_events`，前端上报事件必须使用 9 个 canonical hall slug 或对应中文展厅名。后端不再保留历史 slug 兼容映射，无法归一到 9 个展厅的 hall 值会被丢弃。

目前会计入到访展厅的事件类型：

- `exhibit_question`
- `exhibit_view`

这意味着用户只是进入展厅不会被计入 `halls_visited`；在展厅内发送一条有效问题，或点进该厅任意展品详情页，才会计入对应展厅。确定性要求用户补充对象名称的澄清轮次会从到访展厅、问题数和报告内容中排除。`halls_visited` 按 canonical hall slug 去重。问题数由有效 `exhibit_question` 计数，每条用户发送消息计一次，不对相同问题文本去重。展品浏览由 `exhibit_view` 单独计入展品统计，并按展品去重。

`POST /api/v1/tour/sessions/{session_id}/events` 的 `metadata` 会持久化到事件的 JSON 字段，报告会从其中提取问题、AI 回答、展品和展厅信息。不要把隐私数据、完整 API key 或用户敏感信息放入 `metadata`。

`POST /api/v1/tour/sessions/{session_id}/report` 当前重点返回：

- `halls_visited`：已归一化的到访展厅 slug 列表。
- `highlights`：问题数、展品数等本次导览亮点，不包含到访展厅数量。
- `reflection`：Reflection Engine 规则推断出的认知变化。
- `record_notes`：按展厅合并用户问题和 AI 回答后的记录摘要，供前端直接渲染。
- `exploration_guidance`：以单句 `next_step` 为主，并保留恰好 1 条兼容 `action`；该 action 包含 `title`、`description`、`question`，有可信关联时另带 `hall_id` / `exhibit_id`。

报告生成不新增数据库表、不新增 API，也不改变 SSE 协议。`record_notes` 会优先调用报告模型生成不超过约 300 字的凝练记录摘要；模型不可用或生成失败时回退到规则式摘要，避免报告不可用。

## 环境变量

本地开发可从仓库的示例文件建立仅本机使用的 `.env`。README 不列出具体字段、服务地址、模型、密钥负责人或生产取值；生产配置只保存在服务器受控环境文件中。

```bash
cp .env.example .env
```

`.env` 不允许提交到仓库。线上修改后必须按受控发布流程重启并验证 readiness；额度、账单告警和密钥轮换在私有运维记录中维护。

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
- 小程序统一使用 `https://api.banpo-museai.xyz/api/v1`；旧 `3000` 端口不再作为发布、调试或回退入口。微信开发者工具与真机测试都应验证 HTTPS 域名链路。

2 核 / 8 GB 下的建议：

- 后端优先保持单个 Uvicorn worker，避免 Redis、Elasticsearch、PostgreSQL 与 Python 进程争抢内存。
- RAG、rerank、TTS 均依赖外部服务，线上应控制并发和超时，优先保证小程序导览流式响应。
- Elasticsearch、Redis、PostgreSQL 如与后端同机部署，需要持续观察内存占用；数据量增长后优先拆分检索或数据库服务。

生产发布只使用 systemd 托管，并在切换代码前备份 PostgreSQL；有上传图片时还必须同批次备份持久图片目录。当前精确发布来源为 `origin/main`；必须先 fetch 并记录目标 SHA，不得使用无条件 `git pull`，也不得用进程名 `pkill` 或 `nohup` 启动替代受控发布。

唯一权威的备份、精确 SHA 切换、依赖同步、迁移、systemd 启停、健康检查和回退流程见 [小程序内容维护指南：生产部署和验收](./docs/miniapp-content-maintenance.md#7-生产部署和验收)。`deploy/DEPLOYMENT_NOTES.md` 仅说明 systemd、Nginx、应用日志保留、备份调度和 Swap 配置，不另行定义发布流程。

服务器继续从 `/home/ubuntu/MuseAI` 直接获取精确提交并部署；Git 跟踪内容、服务器本地密钥/运行数据和真实数据更新边界见 [服务器直拉部署与存储边界](./docs/server-storage-layout.md)。禁止在生产 checkout 使用会删除 `.env`、`.venv` 和日志的全量 `git clean`。

## 上线前阻断项

- 微信公众平台 request 合法域名已配置并通过关闭豁免后的真机测试；如后续使用上传/下载文件 URL，再确认 uploadFile/downloadFile 合法域名。
- 前端 API 已从开发 IP 切到 HTTPS 域名。
- 真实馆方展品、图片、地图/点位和空间数据已导入并抽样核验；九厅名称和简介沿用当前已确认口径。
- OCR 上线策略已确定：购买并配置服务 ID，或隐藏 OCR 入口只保留文字搜索。
- Qwen/DashScope 免费额度、付费开通、限流和账单告警已确认。
- API key 负责人和轮换流程已明确。
- 重置曾暴露过的 AppSecret 和 API key。
- 每批生产发布均记录并验证数据库/图片备份、校验和、systemd 健康检查和回退证据。
- 完成 iOS/Android 真机全链路测试：问卷、路线、导览、TTS、OCR、报告。

## 安全注意

- 不提交 `.env`、`.env.backup*`、私钥、AppSecret、LLM key、TTS key。
- 证书私钥只保留在线上服务器安全目录，权限建议 `600`。
- 调试日志中不要输出完整 API key、AppSecret、用户 token 或原始隐私数据。
