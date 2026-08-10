# 后端变更日志

## 2026-08-10

- 修复报告页前置会话同步 422：小程序九厅 `route_plan.steps` 已保存 `short`、`exhibitCount`、`exhibitCountKnown`，后端严格恢复模型此前未声明这三项，导致 9 厅产生 27 条 `extra_forbidden` 并在报告生成前被阻断。`TourRouteStep` 现只新增这三个受约束字段，未知字段仍拒绝，不放宽整体 schema，也不把展示计数作为 Agent 事实。
- 回归契约改为完整九厅路线快照，覆盖九厅逐项 PATCH、GET 等值恢复、旧快照默认值、字段边界和未知字段仍返回 422；`test_tour_api.py` 66 项、完整后端 `1590 passed, 23 skipped, 9 warnings`、scoped Ruff 与 `git diff --check` 通过。小程序 16 组检查与 64 文件发布预检通过。
- 服务器存储方案按审批反馈收敛为最小变化：继续以 `/home/ubuntu/MuseAI` 直接 fetch 精确提交并部署，不迁移 `/srv`、Docker 卷或证书目录。`docs/server-storage-layout.md` 改为 Git/服务器持久内容边界和直接 checkout 流程。
- `.gitignore` 收窄全局 `dist/`、`var/` 与 `docs/reference/**` 规则，恢复所有 npm lockfile 和可公开参考资料的正常跟踪；新增 `.env.*`、证书/私钥、SQLite、备份、上传目录和本地导入文件规则，同时保留真实 museum CSV 可跟踪。移除全仓无引用、误入 Git 的 `test_alembic.db`。
- 服务器直接 checkout 增加目标 tree 受保护路径门禁，并统一使用 `git switch --no-overwrite-ignore --detach`；目标提交若误跟踪 `.env`、`.venv`、日志、证书、上传目录或管理端生成物会在切换前失败，不能覆盖服务器本地内容。部署顺序继续强制先停服务，再同步依赖和迁移。
- 验证通过：ignore 正反契约 18 项、配置/迁移定向回归 `27 passed`、后端全量 `1590 passed, 23 skipped, 9 warnings`、`uv lock --check`、`uv pip check`、scoped Ruff、14 个 Bash 文档块及 2 个部署脚本语法。正式模板 dry-run 为 9 厅/0 展品，联调快照为 9 厅/46 展品，均未连接生产依赖。
- 后端功能提交 `f18a936`、方案提交 `bc2c6fc` 与小程序提交 `1fa24e4` 已分别推送；生产部署到 `bc2c6fc`，发布记录为 `/home/ubuntu/museai-config-backups/release_20260809T232004Z.env`。数据库备份 SHA-256 为 `4ac1cd102b7a4f8f6f9fa2fd0faedb18916296b9284d1158ff1a2fe678753941`，图片备份 SHA-256 为 `77d673e07aa7c5b512affec9facf471829e44a13e6a1df9acfcb8a9dc6267b19`；迁移保持 `20260809_trusted_hall_chat_history (head)`，内网与公网 readiness 均 healthy。
- 公网独立游客会话实测九厅完整路线 PATCH 200、GET 200 且九步字段逐项恢复；未知字段仍返回 422，报告 POST 返回 200。服务工作树干净，发布后关键日志错误计数为 0；探针未输出 token。

## 2026-08-09

- 导览聊天新增确定性 grounding gate，不增加 LLM 分类调用：纯数字/全角数字/序号/标点及无同厅完整问答支撑的泛指直接流式澄清；明确展厅级、类别、唯一展品名称及同厅完整问答追问继续。API 不隐式复用 session 残留 `current_exhibit_id`，多名称匹配最多列出三项要求确认，system prompt 明确禁止把 RAG 首条结果当作用户指代。
- 展厅新增单一持久化字段 `short_description`（最多 48 字）和迁移 `20260809_hall_short_description`；统一 CSV 可选列已为九厅写入一一对应短简介。`/tour/halls` 返回主字段 `short_description` 与同值兼容别名 `card_description`，完整简介保持不变。
- 报告 `exploration_guidance` 新增单句 `next_step`（硬上限 60 字、当前文案目标不超过 30 字），旧 `actions` 收敛为一条。确定性澄清事件携带 `clarification_required=true`，并从问题统计、记录摘要、复盘和探索指导中排除；有效泛指追问使用固定具体指导，不把“为什么/它呢”机械拼入建议。
- 建议条新增 8–18 字具体问句质量边界：过滤过短、模糊、测试数据、真实数据接入和上线流程类文案；展品有可信事实时，按名称、简介细节与分类确定性补齐，不增加运行时 LLM 调用。
- 游览报告新增 `exploration_guidance`：当前以单句 `next_step` 为主，并保留标题、摘要和一条含具体问题的兼容观察任务；可确定时关联展厅/展品 ID，无历史也返回明确起点，不再使用“暂时不生成”类拒绝文案。
- 展品数据新增 `image_url` / `image_path`：CSV/XLSX 可导入 HTTPS 外链，管理员可上传或删除单帧 JPEG/PNG/WebP，公开 API 仅为启用且属于可信九厅的展品提供图片。本地路径不对外暴露，无图时 `image_url` 为 `null`。
- 新增 Alembic 迁移 `20260809_exhibit_images`、图片存储配置和 `docs/miniapp-content-maintenance.md`；生产应使用 Git 工作树外的持久目录，并在代码/数据回退时单独备份与恢复图片文件。
- 建议、报告、导入与图片定向回归 197 项通过；契约修正后相关回归 169 项通过；最终全量回归 `1182 passed, 23 skipped, 10 warnings`，无失败。Ruff、`uv lock --check`、`uv pip check`、Alembic 单一 head 和两个 CSV 数据包 dry-run 均通过。
- 功能提交 `b823bf2` 已推送并部署；生产迁移为 `20260809_exhibit_images (head)`。权威导入更新并重新索引 46 件测试展品，停用 0、待索引 0；九厅、46 展品、92 条建议、公开接口和报告指导内容均通过实测。
- 最新数据库回退基线为 `museai_20260809_094329.sql.gz`（SHA-256 `450d1ab0371ac6d38f73d6b3893747e7e5974c52d0fe2475f19e8b6db626745a`）。生产图片上传烟测因现有唯一管理员口令不匹配而在写入前停止；数据库图片字段和持久目录保持为空，待明确授权处理凭据后补测。
- 本轮未提交、未推送、未部署的后续改动已通过 scoped Ruff 和相关 5 个完整测试文件 `255 passed`（仅 1 条既有 AsyncMock warning）；`/tour` 完整契约 `62 passed`，模板与测试数据 dry-run 分别验证九厅/0 展品和九厅/46 展品，Alembic 单一 head 及从 `20260809_exhibit_images` 到新 head 的离线 SQL 通过。
- 独立复核继续修正未提交实现：代词、比较、序数和“详细一点”类追问只有服务端持久化同厅完整问答才可进入 `history_followup`，客户端单独上传的 `conversation_history` 不能建立指代依据；显式写出两个不同展品名（包括嵌套名称）时不再绑定最长单件。澄清事件不再计入报告到访展厅。
- Hall 导入为可选 `short_description` 增加列存在性：CSV/XLSX 省略整列保留数据库现值，包含空列则显式清空。长展品名在缺少分类和简介锚点时会确定性提取可辨器物名并生成 1–2 条 8–18 字问句，不增加 LLM。相关 4 个完整测试文件 `255 passed`（1 条既有 AsyncMock warning），scoped Ruff、两套数据 dry-run、Alembic 单一 head 与直接降到 `20260809_exhibit_images` 的离线 SQL 均通过。
- 会话恢复与模型记忆完成物理隔离：新增仅服务端写入、API 不暴露的 `trusted_hall_chat_history` 及独立迁移 `20260809_trusted_hall_chat_history`。PATCH 可写的每厅最近 30 条 `hall_chat_history` 只供界面恢复；客户端 `conversation_history` 和伪造 assistant 文本不再进入 prompt、检索改写或 grounding。服务端完成轮次同时写入展示/可信历史，重启后仍可继续同厅追问。
- grounding 改为通用复数、比较、序数、前后、其中/另外和选择指代检测，并在展厅级与已选单展品绑定前处理；明确写出两件对象的比较仍是清晰问题。建议条按编号、出土残片、房址/墓葬/遗址、雕塑/模型/分布图和器物工具选择不同问法，继续拒绝“形制”并接受日常“器形”。CSV/XLSX 显式建议任一无效即整批失败，留空才自动派生；生产文档移除 `pull main`、进程名 `pkill` 和 `nohup` 旧流程。
- 本地未提交、未推送、未部署的最终相关组合为 `261 passed`、无 warning；同时修正测试桩把同步 `AsyncSession.add` 误建为异步 mock 的噪声。scoped Ruff、`uv lock --check`、九厅/0 展品与九厅/46 展品双 dry-run、Alembic 单一 head 和从 `20260809_trusted_hall_chat_history` 直接回退到 `20260809_exhibit_images` 的离线 SQL、`git diff --check` 均通过。
- 独立发布复核后继续修正 grounding 正反语义矩阵：纯选择、中文数词、口语复数、相对位置和示指比较只有服务端完整可信轮次支撑时才延续；量词后含陶器、房址、柱洞、随葬品、保护措施等实义对象，以及明确时期/展厅/工具/区域/纹样 WH 问句保持清晰。明确展厅问题优先于当前单件，且只有 `bound_exhibit` 才向 system prompt、检索查询和事件写入展品上下文/ID。
- 建议派生改为名称主对象优先：模型、雕塑、房址、分布图、编号、石斧、骨针和残片不会因简介提到墓葬区/居住区而生成区域用途题；仅纹饰、磨损等强相关细节可替换第二条。名称正文残留“测试/占位/维护”等噪声时返回空，不把维护命名转成问题。
- 建议导入严格区分整格留空和显式空值：JSON `[]`、空字符串元素以及 `|` / ` || ` 空段在 CSV/XLSX 中都会使整批失败且不写入；版本化两套 `halls.csv` 已改为空单元格。英文 README 删除旧手工部署并同步可信历史、导入、图片和 `next_step`；中文报告与上线口径同步。PostgreSQL 备份改为临时文件、`gzip -t` 后原子发布，发布记录保存备份路径和 SHA-256。
- 本次复核定向测试：聊天 `87 passed`、建议/会话 `95 passed`、导入 `58 passed`、展厅迁移基线 `4 passed`，合计 `244 passed`；scoped Ruff、双数据包 dry-run、`bash -n deploy/pg_backup.sh` 和 `git diff --check` 通过。未执行全量，未提交、未推送、未部署。
- 部署流程 P1 收口：容器备份默认并显式使用 Compose 角色 `museai`；权威发布/回退命令统一 `set -euo pipefail`，以 `0600 current-release.env` 固定指针恢复批次记录并在每个阶段落盘。发布门禁改为 `/api/v1/ready`，权威链路固定为 systemd `127.0.0.1:8000` + HTTPS，旧 3000 必须无监听。新增可执行临时库恢复演练、候选生产库切换及拒绝危险 tar 条目的图片恢复流程；备份成功/失败 mock 回归、2 个脚本 Bash 语法、15 个权威 Bash 文档块语法/fail-closed 检查均通过。未提交、未推送、未部署。
- 建议条复核修正：名称缺失或仅为“图/墓/A/1/-”等单字符噪声时，不再用墓葬区、居住区、陶窑区等弱锚点生成问题；只有名称/分类无安全主体时才从全部简介锚点中筛选强具体细节。新增“示例/样例/模拟/虚拟/临时数据/待补充/demo/test”等噪声识别，标准化前缀标签可剥离后使用真实对象，残留或非标准拼接则整名拒绝。`test_tour_services.py` `119 passed`、导入服务 `58 passed`，相关 Ruff 通过。未提交、未推送、未部署。
- grounding 有限矩阵最终覆盖厅级口语、明确双对象比较、数字/序号多选、复数量词与集合、余项/相对位置、疑问指示、项/点/类别序号和单件示指；186 条独立重放 `186/186`。无同厅完整可信历史时模糊输入澄清，有完整可信轮次才追问；厅级与双名称问题不会携带旧单件 prompt、检索词或事件 ID。
- 会话历史幂等改为服务端可信窗口内的稳定 `turn_id`：同 ID 的相邻或延迟重试保留第一次结果，不同 ID 的完全相同问答仍完整恢复；客户端展示历史提前同步时不会重复。私有 `_turn_id` 不由 PATCH 接受、不由 GET 暴露，也不会进入模型上下文。
- 部署门禁删除 Compose 固定数据库弱口令，缺少 `POSTGRES_PASSWORD` 时 fail-closed；PostgreSQL、Redis、Elasticsearch 使用并现场核对 `restart: unless-stopped`。备份统一经 Bash 调用并使用纳秒文件名，systemd 拉起 Docker，readiness 同时核对 loopback 8000 与当前主进程 PID；README 统一 HTTPS-only。
- 最终全量回归 `1480 passed, 23 skipped, 9 warnings`，无失败；改动文件 Ruff、`uv lock --check`、`uv pip check`、Alembic 单一 head、两套数据 dry-run、直接回退离线 SQL、备份成功/失败 mock、Compose 密码门禁和 `git diff --check` 均通过。9 条 warning 为既有测试桩或第三方弃用提示。
- 生产部署现场发现 Compose 与应用共用 `.env` 时，严格 Settings 会拒绝 `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`。现已显式声明三项且保持未知字段 fail-closed；三项必须成组、非空，并与解码后的 PostgreSQL `DATABASE_URL` 用户、密码和库名完全一致。数据库 URL、数据库密码及 JWT/LLM/Embedding/Rerank/TTS 密钥不进入 Settings 的 `repr`/`model_dump`，启动异常字符串隐藏原始输入；伪 `postgresqlx` 驱动会被拒绝。
- 部署文档删除不存在的 `systemctl is-inactive`，所有非登录 SSH 发布/回退命令先进入项目目录并使用 `/home/ubuntu/.local/bin/uv` 绝对路径。最终相关配置/provider 回归 `86 passed`，独立审查 P0/P1/P2 均为 0；使用仓库内专用 pytest 临时目录的最终全量回归 `1492 passed, 23 skipped, 9 warnings`，无失败。首次全量的 50 个 setup error 已确认仅来自 Windows 全局 pytest 临时目录 ACL，隔离后未复现。
- 导览会话继续以服务端可信历史为唯一指代依据，并为每轮持久化 `single` / `multi` / `hall` / `unknown` 对象范围、单件展品 ID 和澄清标记；这些私有字段不进入恢复 API 或模型正文。页面选中的展品与本轮问题对象分离：选中 A 后明确询问 B 只绑定本轮 B，恢复状态仍为 A；“它和 B”改写为明确 A/B 比较且不绑定单件，“它是不是 B”按 A 与 B 的身份核对处理。
- grounding 补齐无依据代词、复数、序数、相对位置、双示指、选择项和模糊比较的收口规则；只有最近可信回答实际给出对应编号或兼容对象范围时才能延续。明确展品名、厅级问题、含实义对象的量词/WH 问句和正常包含“同一、相同、和平、和谐、比较”的表达不会被比较连接词误切分。
- 模型输出若本身是在要求补充展品名称，也会统一标记为澄清；报告侧同时识别中英文问号、感叹号等句末标点，确保澄清轮次不进入问题数、到访展厅、记录摘要、复盘或下一步指导。
- 最终冻结代码通过会话/报告/契约定向回归 `549 passed`、日志与 TTS 组合 `90 passed`、scoped Ruff 和 `git diff --check`；完整后端回归为 `1589 passed, 23 skipped, 9 warnings`，无失败。独立复核未发现 P0/P1；保留两个低优先级技术债：每厅 30 条可信消息窗口外的极旧 `turn_id` 重试无法永久去重，以及每次非厅级对话仍会加载当前厅全部启用展品用于名称匹配。
- 功能提交 `033d3061eaade54b21176620bd8f533c9d7fddb4` 已推送并部署。发布记录为 `/home/ubuntu/museai-config-backups/release_20260809T114910Z.env`；数据库备份 `/home/ubuntu/museai-backups/museai_20260809_194910_242951323.sql.gz` 的 SHA-256 为 `3f978008cac0e129d751b28a886893967b9e107d5f6472a420b87d98e76db9ce`，图片备份 SHA-256 为 `77d673e07aa7c5b512affec9facf471829e44a13e6a1df9acfcb8a9dc6267b19`。迁移保持 `20260809_trusted_hall_chat_history (head)`，loopback 与公网 readiness 均为三项依赖 healthy，旧 3000 无监听。
- 公网综合探针验证展厅问题、无依据追问、选中 A 后明确询问 B、A/B 比较、双示指比较、报告排除澄清、每厅恢复历史和私有字段不泄漏均通过；报告只统计 1 个有效问题。SSE TTS 返回 4,392,960 字节有效 PCM，独立 TTS 返回 122,924 字节结构有效 WAV。
- 生产 TTS 音频本身正常，但文本文件日志 formatter 会把已经渲染的 `prompt.variables` 字典大括号再次作为 Loguru 模板解析，触发 `KeyError: "'name'"`。提交 `fd96e17fd88ebd4d7426cee4bf8794a1c57c3871` 改为固定 `{message}` 模板并新增 `catch=False` 回归；部署后真实 TTS 返回 92,204 字节有效 WAV，日志中 `Logging error`、`KeyError`、`Traceback` 均为 0。
- 最新日志修复发布记录为 `/home/ubuntu/museai-config-backups/release_20260809T120456Z.env`；数据库备份 `/home/ubuntu/museai-backups/museai_20260809_200456_436886593.sql.gz` 的 SHA-256 为 `d7f8efcdaa5c5c0e9e6b9795cc2ddfad286f837f32ca803b3e2bfa653c8ead8c`，图片备份 SHA-256 仍为 `77d673e07aa7c5b512affec9facf471829e44a13e6a1df9acfcb8a9dc6267b19`。迁移与三项依赖 readiness 保持 healthy。

## 2026-08-08

- 将生产库 46 条无来源旧演示展品整理为 `data/museum_test_data` CSV 快照：名称、介绍、分类和稳定记录 ID 均明确标记为测试数据，并均匀分配到九个可信展厅；使用稳定来源 `banpo-museum-data`，后续真实权威快照可自动替换。
- 测试数据 CSV 与空展品正式模板均通过 dry-run；导入专项 33 项、展厅迁移专项 4 项通过，最终全后端回归 `1156 passed, 23 skipped, 10 warnings`，`uv lock --check`、`uv pip check` 和 `git diff --check` 通过。
- 生产部署升级到迁移 `20260808_remove_legacy_halls`；权威导入更新九厅、创建并索引 46 条测试展品、停用 46 条旧记录，`pending_index=[]`。数据库、ES、公开 API、30 条同厅恢复、OCC 冲突、SSE、报告归纳和双次有效 WAV 均通过实测。
- 生产管理员收敛为仅 `test@test.com`；原 `admin@museai.local` 降为普通用户而未删除。部署前备份为 `museai_pre_test_import_20260808_164810.sql.gz`，SHA-256 `689896c85cd13d007c03049dc71c3d377a93f31754773f8a976183a1976517fe`。
- 将九个已确认展厅 slug 固定为小程序可信白名单，名称与简介只从 Hall 数据读取；新增前向迁移和 CSV 基线一致性测试，楼层与参观时长以 `NULL`/`0` 表示尚未接入真实路线数据。
- 公开展品、游客会话、事件、建议条、聊天展品上下文和 RAG 关联文档统一要求“展品启用、展厅存在且启用、属于九厅白名单”；旧厅、停用厅、孤立展品和缺失 Hall 的关联文档均 fail-closed。
- 每厅恢复最近 30 条对话；推理保留最近 10 条原消息，将此前最多 20 条确定性压缩为一条普通历史消息，不跨厅、不新增摘要 LLM 调用。
- 临展厅一、二使用同一动态模板，仅拼接各自当前启用展品；上传、停用或删除后自动反映，不跨厅取数。
- 删除旧演示展品和破坏性初始化/导入脚本；正式数据统一使用 `data/museum_template` 的 CSV/XLSX 格式和幂等导入管线。
- 修复 SSE/TTS 资源回收、WAV/PCM 缓存边界及报告摘要归纳与并发更新；小程序传入文本不再提升为 system prompt。
- 定向最终回归：`152 passed`；新增 RAG owner、孤立展品 chat、九厅迁移/CSV 同步回归均通过。最终全量回归：`1155 passed, 23 skipped, 10 warnings`，无失败；scoped Ruff、`uv lock --check`、`uv pip check`、Alembic 单一 head 与模板 dry-run 均通过。提交、推送与部署结果在完成后补记。

## 2026-07-15

- 建立数据驱动后端框架任务。
- 确认 Excel/CSV 输入、纯游客 session、A/B/C/D 问卷人格、动态报告和 2C8G 资源基线。
- 新增纯游客 session token、完整恢复状态、每展厅最近 20 条会话和最多 9 个展厅的恢复上限，并以状态版本防止并发覆盖。
- 快速开始使用独立 `default` 人格；问卷使用 A/B/C/D；删除公开注册入口，普通账号不能登录，管理员由引导脚本初始化。
- 新增 Excel/CSV 馆方数据校验、幂等导入、来源追踪、RAG 激活回滚与数据驱动建议问题。
- 对话只从数据库读取可信展厅/展品事实；报告重复打开时按当前时间刷新总时长。
- 数据库迁移 head：`20260715_data_driven_tour`。
- 验证：最终 focused 后端测试 205 passed；本次变更 Python 文件 Ruff 通过；Alembic 单一 head。
- PATCH 会在写入前校验当前展品真实存在、处于启用状态且属于有效展厅；仅切换展厅时也校验保留展品，避免无效外键或跨厅状态。
- 数据导入在写入前拒绝同来源、同展厅 slug 改换非空 `source_record_id`；相关 API/导入 focused 测试 52 passed，scoped Ruff 通过。
- 创建游客会话与生成报告的 POST 路由已接入独立限流依赖；报告生成同时传入数据库展厅名称映射；限流依赖测试 46 passed。
- 报告首次并发生成时复用唯一报告记录；Nginx 在读取游客状态前执行 2 MiB 限制；动态总时长保证不出现负数。
- 补充超过 24 小时后的同值开始时间恢复、人格不可变、任意风格文本拒绝及导入展厅真实名称进入报告摘要的回归测试。
- 修复同批次停用展厅与展品时的组合回滚：某展品旧 RAG 删除失败时恢复该展品及所属展厅原 active 状态，其他成功删除的展厅/展品仍正常停用；importer 测试 20 passed。
- 公开展品 catalog、筛选与普通名称搜索统一采用馆方 `display_order` 升序、空值后置，再以创建时间和 ID 稳定兜底；Hall 表有记录但全部停用时返回空列表，不再复活静态展厅；相关真实 repository/API/Tour 测试 65 passed。
- 新增显式 `--authoritative` 完整快照接管：默认导入仍非破坏；权威模式只停用同来源遗漏项和无来源旧占位项，其他来源不变。停用旧展品前同时清理 exhibit source 与旧 `document_id/document` 向量，任一删除失败恢复对应展品和展厅并非零退出，不删除 Document/IngestionJob 数据库记录。
- 移除公开展品名称黑名单；同名真实馆方记录正常显示，列表 `total` 与数据库分页结果一致。
- `/tour/halls` 以单批展品查询返回真实 `highlights`（最多 3 条）和由 Hall.description 截取的 `focus`；空展厅不填入假展品。
- 报告展品浏览数只统计真实 `exhibit_id`；移除固定展厅权重、旧占位事实模板和文化特定身份标签。一句话、标签、复盘及记录摘要改为确定性统计、实际问答和数据库展厅名，不再为报告调用 LLM。
- 对话检索会按 `Exhibit.document_id` 校验旧 document 分片，仅允许当前展厅启用展品关联的分片，同时保留未关联展品的通用馆方文档。
- 最终验证：关键组合 159 passed；全后端 1073 passed、23 skipped（17 条既有 warning）；本次变更 scoped Ruff 与 `git diff --check` 通过。
- 提交 SHA：见本提交。推送分支：`codex/data-driven-miniapp-framework`。

## 2026-07-16

- 生产部署验证发现长期运行的 `uv run uvicorn` 会使新的 `uv run` 运维命令等待；systemd unit 改为直接调用 checkout 内 `.venv/bin/alembic` 和 `.venv/bin/uvicorn`。
- 部署说明补充每次切换提交后先执行 `uv sync --frozen`，确保 systemd 使用的虚拟环境与目标提交一致。
- PostgreSQL、Redis 与 Elasticsearch 的 Compose 端口只绑定 `127.0.0.1`，避免无认证基础服务暴露到公网。
- 修复生产依赖不可复现：停止忽略并提交 `uv.lock`，部署时先执行 `uv lock --check`、`uv sync --frozen` 和 `uv pip check`，避免服务器旧锁遗漏 `openpyxl` 等运行时依赖。
- 会话恢复允许保留已经下线展厅的历史聊天（每厅仍限制最近 20 条、总计最多 9 厅），但当前展厅和当前展品继续按启用数据严格校验。
- 会话 PATCH 对同值快照和不可写字段不再推进 `state_version` 或刷新活动时间，避免重复异步同步制造无意义的 OCC 冲突。
- 导览 SSE 在 `done` 前分别尝试持久化问答事件和展厅历史，返回最后成功写入的 `state_version`；助手事件使用与小程序一致的稳定 ID，支持前后端跨侧去重，单项持久化失败仍保持流式响应可完成。
- Excel/CSV 导入把非 UTF-8、畸形 CSV、损坏 XLSX 和缺失工作簿结构统一转换为结构化校验失败；单次文件及导入后的数据库最多保留 2000 个启用展品。
- 公开展品列表和详情新增数据库驱动的 `hall_name`；列表使用单次批量查询，未知展厅名退回规范化展示名。
- 数据导入 CLI 已分别验证 CSV、权威 CSV、XLSX 正常 dry-run，以及非法来源名、非 UTF-8 CSV、畸形 CSV、损坏 XLSX 的非零结构化失败。
- 最终验证：完整后端串行测试 `1088 passed, 23 skipped, 17 warnings`；23 项均因本机未启动 PostgreSQL、Elasticsearch、Ollama 或 Redis 而跳过，小程序核心测试无跳过。Python 3.11 与 3.12 变更组合各 `174 passed`；`uv lock --check`、两版本 `pip check`/`compileall`、scoped Ruff、mypy、Alembic 单一 head 和 `git diff --check` 均通过。
- 报告记录摘要改为受约束的单次报告模型归纳：system 仅保存规则，后端持久化问答与数据库展厅名作为不可信结构化 JSON；按截断后的规范输入 SHA-256 指纹更新，模型失败或输出逐轮复述时回退为确定性的主题/结论语义合并。
- 新增 `tour_reports.record_summary_source_hash` 迁移；未回答问题只更新报告统计，不触发摘要 LLM。POST/GET 报告共用限流，调用 LLM 前释放事务，返回后按 session→report 锁序重读最新状态，过期摘要不得覆盖并发的新事件、session 字段或较新报告。
- `record_events` 在查重与插入前锁定 session 行，预生成稳定事件 UUID，并把加锁、重查、重建和提交作为完整重试单元；即使提交结果不明也能按主键/client ID 收敛，离线补传不会重复。
- TTS 流式 PCM16 与文件 WAV 缓存按规范 JSON 模式键隔离；缓存和上游 WAV/PCM 均做格式校验。独立接口使用 token 哈希 30/min + 共享 IP 300/min 双层限流，无 token 时保留 IP 桶；文本、voice、style、persona 均加边界，失败日志不记录文本/token。
- 小程序聊天 message 去除首尾空白并要求 1–2000 字，纯空白在进入付费 LLM 前返回 422。
- 本轮定向组合验证 `230 passed`（7 条既有 warning）；最终全后端串行测试 `1124 passed, 23 skipped, 13 warnings`，跳过项均因本机未启动 PostgreSQL、Elasticsearch、Ollama 或 Redis。scoped Ruff、Alembic 单一 head `20260716_report_summary_hash` 与 `git diff --check` 通过。
