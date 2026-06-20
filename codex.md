# Codex 工作报告

## 2026-06-19 后端自测与 README 同步

### 自测结果

- Python 编译检查通过：
  - `backend/app/api/tour.py`
  - `backend/app/application/tour_report_service.py`
  - `backend/tests/unit/test_tour_services.py`
  - `backend/tests/contract/test_tour_api.py`
- 报告相关单元测试通过：
  - `uv run pytest backend/tests/unit/test_tour_services.py -k "aggregate_stats or collect_qa_pairs or record_summary" -q`
  - 结果：8 passed, 39 deselected。
- 报告相关契约测试通过：
  - `uv run pytest backend/tests/contract/test_tour_api.py -k "report" -q`
  - 结果：5 passed, 18 deselected。
- 全量后端测试通过：
  - `uv run pytest -q --basetemp .pytest-tmp`
  - 结果：1021 passed, 23 skipped。

### 说明

- 直接执行 `uv run pytest -q` 时，Windows 旧 pytest 临时目录被其他进程锁住，触发 `PermissionError: WinError 5`；使用 `--basetemp .pytest-tmp` 隔离后全量通过。
- 测试完成后已清理 `.pytest-tmp`。

### 文档更新

- `README.md` 和 `README_EN.md` 已同步当前报告事件契约：
  - `halls_visited` 只由 `assistant_answer` 计入。
  - `exhibit_view` 单独计入展品统计。
  - `exhibit_question` 不直接增加问题数或到访展厅。
  - `record_notes` 优先使用报告模型生成，失败时回退规则式摘要。
- 同步备案期间 HTTP 调试入口与正式 HTTPS 切换要求。
- 补充 Windows pytest 临时目录锁定时的 `--basetemp` 复测方式。

### 注意事项

- 本轮未 commit、未 push、未修改真实 `.env`。
- 未改 SSE 协议、未改数据库 schema。

## 2026-06-19 统计规则重对齐

### 修改

- `backend/app/api/tour.py`
  - `halls_visited` 从 `exhibit_question`、`exhibit_view` 和历史兼容的 `assistant_answer` 中收集，并按 canonical slug 去重。
- `backend/app/application/tour_report_service.py`
  - `total_questions` 改为统计用户发送消息数，即 `exhibit_question` 事件数量。
  - 问题数不按文本去重。
  - `total_exhibits_viewed` 继续按展品 ID 或展品名称去重。
- `backend/tests/unit/test_tour_services.py` 和 `backend/tests/contract/test_tour_api.py`
  - 更新为新统计口径：展厅/展品去重，问题不按文本去重。

### 验证

- `uv run python -m py_compile backend/app/api/tour.py backend/app/application/tour_report_service.py backend/tests/unit/test_tour_services.py backend/tests/contract/test_tour_api.py` 通过。
- `uv run pytest backend/tests/unit/test_tour_services.py -k "aggregate_stats or collect_qa_pairs or record_summary" -q` 通过。
- `uv run pytest backend/tests/contract/test_tour_api.py -k "report" -q` 通过。

## 2026-06-19 AI 回答速度问题排查

### 后端检查

- 检查 `backend/app/api/tour.py`、`backend/app/application/tour_chat_service.py`、`backend/app/application/tour_report_service.py`。
- 确认本次问题不来自后端 SSE 协议变更：`/tour/sessions/{session_id}/chat/stream` 仍返回 `StreamingResponse`，`ask_stream_tour` 和 RAG streaming 未在本轮修改。
- 后端 `TourChatHistoryItem.content` 契约限制为单条最多 1000 字。前端恢复展厅历史对话后若直接发送 1600 字长回答，会触发请求体验证失败。
- 近期后端 diff 主要集中在报告统计口径与报告摘要，不在导览回答热路径。

### 处理

- 后端未改代码。
- 性能修复落在前端 `pages/tour/tour.js` 的流式渲染与滚动节流，以及 `store/chat.js` 的历史对话请求体压缩。

## 2026-06-19 报告问题统计去重修复

### 问题

报告页的问题数可能高于用户实际完成的 AI 问答次数。后端已经只统计 `assistant_answer`，但同一回答如果因为网络重试等原因以不同 `client_event_id` 被重复保存，仍可能被多算。

### 修复文件

- `backend/app/application/tour_report_service.py`
- `backend/tests/unit/test_tour_services.py`

### 修复内容

- 新增 `_answered_question_dedupe_key()`。
- 报告统计的 `total_questions` 改为按“展厅 + 问题文本”对 `assistant_answer` 语义去重。
- 保持 `exhibit_question` 不直接计入问题数。
- 增加不同 `client_event_id` 的重复 `assistant_answer` 只计一次的单元测试。
- 未修改数据库 schema、SSE 协议或 RAG 流程。

### 验证

```bash
uv run python -m py_compile backend/app/application/tour_report_service.py backend/tests/unit/test_tour_services.py
uv run pytest backend/tests/unit/test_tour_services.py -k "aggregate_stats or collect_qa_pairs" -q
uv run pytest backend/tests/contract/test_tour_api.py -k "report" -q
```

结果：全部通过。
## 2026-06-20 报告统计、展厅到访与记录摘要修复

### 修改文件

- `backend/app/api/tour.py`
- `backend/app/application/tour_chat_service.py`
- `backend/app/application/tour_report_service.py`
- `backend/tests/unit/test_tour_services.py`
- `backend/tests/contract/test_tour_api.py`

### 修改内容

- `TourChatRequest` 增加 `client_event_id`，`ask_stream_tour()` 在自动记录 `exhibit_question` 时复用前端传入的 ID。
- 报告问题数改为统计用户发送消息数，即 `exhibit_question` 事件数；同一 `client_event_id` 的重试只算一次，历史无 ID 事件不按问题文本去重。
- 报告展厅数只由 `exhibit_question` 和 `exhibit_view` 产生，不再由 `assistant_answer` 或 `exhibit_deep_dive` 单独产生。
- 展品统计继续按真实 `exhibit_id` 去重；本地/mock 展品使用 `metadata.exhibit_name` 作为去重 fallback。
- 记录摘要上限从 260 字扩展到 400 字；`collect_qa_pairs()` 保留所有已回答轮次，只去掉同一 `client_event_id` 的重试，避免相同主题连续追问被折叠。
- API 兜底 `record_notes` 也同步到 400 字，并优先用已回答轮次生成，不再按问题文本合并。

### 验证

```bash
$env:UV_CACHE_DIR='.uv-cache-codex'
uv run python -m py_compile backend/app/api/tour.py backend/app/application/tour_chat_service.py backend/app/application/tour_report_service.py backend/tests/unit/test_tour_services.py backend/tests/contract/test_tour_api.py
uv run pytest backend/tests/unit/test_tour_services.py -k "aggregate_stats or collect_qa_pairs or record_summary" -q --basetemp .pytest-tmp-codex-unit
uv run pytest backend/tests/contract/test_tour_api.py -k "report" -q --basetemp .pytest-tmp-codex-contract
```

结果：语法检查通过；单元测试 9 passed；契约测试 5 passed。

### 备注

- 未修改 DB schema、SSE 协议或 RAG 流程。
- 本轮测试使用仓库内 `.uv-cache-codex` 与 `.pytest-tmp-codex-*`，避免断电后沙箱用户访问旧 `.pytest_tmp` 权限失败。
## 2026-06-20 报告问题数翻倍兼容修复

### 范围

- 复查报告 `total_questions` 与用户实际 AI 提问次数不一致的问题。
- 不修改 DB schema、SSE 协议、RAG 流程或真实 `.env`。

### 修改

- `backend/app/application/tour_report_service.py`：`aggregate_stats()` 继续以 `exhibit_question` 作为问题数来源，但增加短时间重复事件兼容规则。
- 兼容规则只合并“同一展厅、同一问题、15 秒内，并且其中一条带当前前端 `*-question-*` client event id”的重复记录；普通历史无 ID 问题和用户真实重复提问仍逐条计数。
- 去重窗口优先读取 `client_event_id` 前缀中的原始毫秒时间，避免前端 pending 事件在报告页才上传时被数据库 `created_at` 拉开时间差。
- `backend/tests/unit/test_tour_services.py`：增加当前前端 question client id 与后端重复记录相撞时只算一次的回归测试。

### 验证

```bash
$env:UV_CACHE_DIR='.uv-cache-codex'
uv run python -m py_compile backend/app/application/tour_report_service.py backend/tests/unit/test_tour_services.py
uv run pytest backend/tests/unit/test_tour_services.py -k "aggregate_stats" -q --basetemp .pytest-tmp-codex-unit
uv run pytest backend/tests/contract/test_tour_api.py -k "report" -q --basetemp .pytest-tmp-codex-contract
```

结果：语法检查通过；`aggregate_stats` 单测 6 passed；报告契约测试 5 passed。

## 2026-06-20 管理端与后端展品命名统一

### 范围

- 用户指出小程序和管理端语义只涉及“展品”，旧称不应再保留。
- 本轮只做命名清理，不修改 DB schema、API 契约、SSE 协议或 RAG 流程。

### 修改

- `backend/app/application/tour_chat_service.py`
  - 后端导览提示词中的旧称统一为“展品”。
- `frontend/src/components/admin/ExhibitManager.vue`
  - 管理端展品管理标题、统计卡片、批量绑定/停用提示、筛选项和表格列统一为“展品”。
- `frontend/src/components/admin/MiniProgramControlPanel.vue`
  - 小程序闭环说明中的数据与报告统计文案统一为“展品”。
- `frontend/src/components/admin/TourPathManager.vue`
  - 路线表格中的统计列统一为“展品数”。
- `frontend/src/components/tour/HallSelect.vue`
  - 管理端/旧 Web 展厅选择展示中的标签统一为“展品”。
- `docs/banpo_data_audit.md`
  - 数据审计文档统一为“展品知识库”。

### 待验证

- 已完成。

### 验证

```bash
$env:UV_CACHE_DIR='.uv-cache-codex'
uv run python -m py_compile backend/app/application/tour_chat_service.py
cd frontend
npm.cmd run build
cd ..
rg -n "展项" backend frontend docs -S
```

结果：Python 语法检查通过；管理端 Vite build 通过。Vite 仅提示 Element Plus vendor chunk 超过 500 kB，为现有依赖体积警告。残留关键字扫描无命中。
