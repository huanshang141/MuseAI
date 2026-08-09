# 服务器测试数据与部署检查点

- 目标：以九个可信展厅和分厅测试展品验证数据驱动小程序框架；仅允许 `test@test.com` 登录管理接口；完成迁移、导入、报告、建议与图片链路验收。
- 本地后端：`codex/data-driven-miniapp-framework`；新框架收口已通过最终门禁，等待提交和推送。线上仍保持可回退基线 `b823bf2fd5b3924c481cc5080f82e6d4e8a7242e`。
- 小程序：唯一分支 `main`，最终提交 `99307705ace8ec66c0bcde80420067ac27b89ad5` 已推送到 `origin/main`，工作树干净。
- 生产后端：`/home/ubuntu/MuseAI` 检出同一功能提交，工作树干净；`museai-backend` active，迁移为 `20260809_exhibit_images (head)`。
- 最新回退基线：`/home/ubuntu/museai-backups/museai_20260809_094329.sql.gz`，SHA-256 `450d1ab0371ac6d38f73d6b3893747e7e5974c52d0fe2475f19e8b6db626745a`；图片持久目录为 `/home/ubuntu/museai-data/exhibit-images`。
- 数据约定：来源固定为 `banpo-museum-data`；后续真实权威快照沿用该来源和稳定 `source_record_id`，即可自动更新并停用本次测试快照中遗漏的记录。
- 资源约束：2C8G；导入与索引串行执行。导入后 7.25 GiB 内存约 1.9 GiB 已用、5.1 GiB 可用，系统负载约 `0.07 / 0.17 / 0.10`。

## 已完成

1. 生成并验证 `data/museum_test_data/{halls,exhibits}.csv`：九厅共 46 件显式测试展品，每件 2 条具体问题，共 92 条且互不重复。
2. 本地最终全量回归 `1182 passed, 23 skipped, 10 warnings`；Ruff、`uv lock --check`、`uv pip check`、Alembic 单一 head 和模板/测试数据 dry-run 通过。
3. 完成生产备份、依赖同步、迁移、服务重启和权威导入：更新并重新索引 46 件，停用 0，`pending_index=0`；46 条旧记录继续保持非活动状态。
4. 生产公开 health、九厅目录、46 件展品、运行时建议和报告通过。报告返回 `exploration_guidance`，不再输出“已到访展厅”。
5. `admin` 角色仅有 `test@test.com`；遗留 `admin@museai.local` 为普通用户，登录接口会拒绝非管理员。
6. 图片上传烟测在写入前停止：现有 `test@test.com` 密码哈希与已知口令不匹配。数据库图片字段和持久目录均为空，未改线上图片状态；需取得当前密码或经用户明确授权重置后再执行 upload → public GET → DELETE。
7. 当前最终后端全量回归 `1480 passed, 23 skipped, 9 warnings`，无失败；186 条 grounding 独立矩阵和 8 条 turn-id 封闭探针全部通过，独立复核为 P0/P1/P2 均 0。

## 待完成

1. 经用户确认管理员凭据处理方式后，完成一次生产图片上传、公开读取、删除和空状态恢复烟测。
2. 提交并推送当前后端稳定快照；先备份生产数据库和图片目录，再部署到迁移 `20260809_trusted_hall_chat_history`（包含前序 `20260809_hall_short_description`）并重新导入九厅 CSV。

## 2026-08-09 本地后续检查点（未部署）

- 建议条契约统一为 8–18 字具体问句；测试 CSV 46 件展品共 92 条问题。真实展品即使没有分类和简介锚点，长名称也会按标注、自然分隔符和器物名称结尾提取可辨对象，确定性生成 1–2 条问题。
- 聊天增加无额外 LLM 的 grounding gate；数字、标点和无依据泛指不进入 RAG，只有服务端持久化的同厅完整问答可建立 `history_followup`。唯一名称可绑定，部分名称多匹配要求确认；显式写出两个不同展品名时作为比较问题进入 RAG，不绑定最长单件，也不隐式复用 session `current_exhibit_id`。
- Hall 增加可空 `short_description` 单列；Alembic 新 head 为 `20260809_trusted_hall_chat_history`，其前序为 `20260809_hall_short_description`。九厅 CSV 均已填写短简介，公开 API 另返回同值 `card_description` 兼容别名。
- Hall 导入对可选短简介区分“省略整列”和“包含空列”：前者保留数据库现值，后者显式清空，CSV/XLSX 均有回归。
- 报告新增单句 `next_step`，旧 `actions` 只保留一条；澄清事件从计数、摘要、复盘、指导和到访展厅中排除。
- 展示恢复历史与模型可信历史已分为两个数据库字段。PATCH/GET 只涉及每厅最近 30 条展示历史；模型 prompt、检索改写和指代判断只使用服务端完成轮次写入的可信历史，客户端伪造 assistant 文本无法进入推理链路。
- 指代分类覆盖复数、比较、序数、前后、其中/另外与选择表达，并优先于展厅级和已选单展品绑定；建议条按编号、残片、遗址类、图示/模型类和器物工具类生成不同问题。显式建议执行整批严格校验，留空才自动派生。
- 验证：最终全量 `1480 passed, 23 skipped, 9 warnings`，无失败；相关稳定组合 `525 passed`，grounding 精确矩阵 `186/186`，turn-id 封闭探针 `8/8`。scoped Ruff、`uv lock --check`、`uv pip check`、两套 CSV dry-run、Alembic 单一 head 与直接降到 `20260809_exhibit_images` 的离线 SQL、备份/Compose 门禁及 `git diff --check` 均通过。

## 独立发布复核修正（未部署）

- grounding 以强上下文信号→实义对象→可信历史的顺序分类；选择型、口语复数、相对/示指比较有完整可信轮次才延续，量词+明确对象和明确 WH 检索问句保持清晰。只有 `bound_exhibit` 会把单件上下文/ID写入 prompt、检索和事件。
- 建议条始终以名称主对象为中心，简介里的墓葬区/居住区/陶窑区不再独立成题；测试/维护名称噪声不派生。显式空建议在 CSV/XLSX 整批拒绝，只有整格留空才自动派生。
- `pg_backup.sh` 使用同目录临时文件，gzip 完整性校验后原子发布；发布记录保存备份路径与 SHA-256。中英文 README 和 systemd `.env` 注释已同步当前事实。
- 定向结果：`test_tour_chat.py` 87 项、`test_tour_services.py` 95 项、`test_museum_data_import_service.py` 58 项、展厅迁移基线 4 项，共 244 项通过；scoped Ruff、两个权威 dry-run、备份脚本 Bash 语法和 diff 检查通过。全量由总控执行。

## 部署流程 P1 修正（未部署）

- `pg_backup.sh` 的容器内默认角色由错误的 `postgres` 改为 Compose 实际角色 `museai`，所有运维示例仍显式传入 `PGUSER=museai`。
- 权威发布和回退命令统一 fail-closed；固定 `0600 current-release.env` 指向当前批次记录，`DEPLOY_STAMP`、备份、目标 SHA 和每个 `DEPLOY_PHASE` 均持久化，可在 SSH 断线后恢复。
- `/health` 仅作存活检查，`/ready` 才是依赖和发布门禁；systemd `127.0.0.1:8000` 与 HTTPS 是唯一权威链路，旧 3000 必须关闭。
- 恢复流程先在随机临时库完成恢复、schema/revision 校验并删除临时库；生产恢复先验证候选库并保留旧库，图片恢复校验 SHA-256、路径和条目类型且保留旧目录。
- 验证：`deploy/pg_backup.sh` 与 `deploy/test_pg_backup.sh` 均通过 `bash -n`；mock 成功路径核对 `docker exec ... -U museai` 和有效 gzip，失败路径非零且无最终/临时文件；15 个权威 Bash 文档块均通过语法和 `set -euo pipefail` 检查。未提交、未推送、未部署。

## 建议条噪声复核（未部署）

- 缺失或单字符噪声主体不能再借墓葬区、居住区、陶窑区等弱锚点生成问题；从简介兜底时会遍历并只保留鱼纹、磨痕等强具体细节，安全内容为空则返回空列表。
- “示例/样例/模拟/虚拟/临时数据/待补充/demo/test”等标准化括号或分隔前缀可剥离后使用真实对象；标签残留、直接拼接或位于名称正文时拒绝整个名称，标签不会进入建议文案。
- 验证：`test_tour_services.py` 119 项、`test_museum_data_import_service.py` 58 项通过；相关 Ruff 通过。
