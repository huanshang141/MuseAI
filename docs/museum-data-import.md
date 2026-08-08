# 博物馆数据导入规范

小程序运行数据支持两种等价输入：一个 `museum_data.xlsx`，或同一目录中的
`halls.csv` 与 `exhibits.csv`。CSV 必须使用 UTF-8（可带 BOM）；Excel 必须且只能包含
`halls`、`exhibits` 两个工作表。表头顺序不限，但字段必须完整且不得增加未知字段。

仓库内 `data/museum_template/` 是可直接校验的基线 CSV：包含已确认的九个展厅，
`exhibits.csv` 只有表头，不含任何演示展品。接入馆方数据时复制该目录并向展品表填入真实记录。

## halls 表头

```text
source_record_id,slug,name,description,floor,estimated_duration_minutes,display_order,is_active,suggested_questions
```

- `source_record_id`：馆方数据中的稳定主键，后续更新不得改变。
- `slug`：小写英文或数字，以单个连字符分隔，最长 100 字符；作为展厅 API 标识。
- `floor` 可留空；时长为 0–480 分钟（`0` 表示尚未确认，小程序不展示预计时长）；`display_order` 为非负整数。
- `is_active` 支持 `true/false`、`1/0`、`yes/no`、`是/否`。
- 数据库一旦存在展厅记录即以其为准；若全部标记为停用，小程序展厅列表为空，不再回退静态开发数据。
- `suggested_questions` 可写 JSON 字符串数组，或使用 `|` 分隔；最多 6 条，每条最多 200 字。
- 小程序完整恢复最多覆盖 9 个展厅，因此一次导入最多只能有 9 个 `is_active=true` 的展厅。
- 当前小程序只识别基线模板中的九个 slug；其他合法 slug 可由管理侧保留审计，但不会进入游客展厅、会话或公开展品接口。

## exhibits 表头

```text
source_record_id,name,description,hall,floor,category,era,importance,estimated_visit_time,display_order,location_x,location_y,is_active,suggested_questions
```

- `hall` 必须引用本次 halls 数据中的 `slug`；启用的展品不能引用停用展厅。
- `importance` 为 0–100；`estimated_visit_time` 单位为秒，可留空。
- `location_x/location_y` 可留空，用于后续馆内路线与定位。
- `source_record_id` 与命令行 `--source-name` 共同生成稳定展品 UUID。
- 单次文件以及导入完成后的数据库最多保留 2000 个启用展品；超出时校验失败，需先显式停用旧展品。
- 小程序普通展品列表、筛选和名称搜索按 `display_order` 从小到大展示；空值排在显式顺序之后，同序时依次按创建时间和稳定 ID 排序。

## 执行流程

先做不连接数据库和检索服务的完整校验：

```powershell
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-2026 --dry-run
```

校验通过后执行导入：

```powershell
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-2026
```

正式导入必须配置 PostgreSQL、Elasticsearch 和 embedding provider。导入采用非破坏性幂等
upsert：文件中缺少的旧记录不会被删除，只有显式 `is_active=false` 才停用。新增或内容变化的
展品只有在旧索引成功移除后才会提交新数据，并先以 inactive 状态写入 PostgreSQL；RAG
重建成功后才激活。如果旧索引无法删除，原数据库版本和 active 状态保持不变，避免数据库
声称停用而旧内容仍可被检索；如果新索引失败，新版本则保持 inactive，并尝试清理已写入的分片；
若分片清理本身也失败，失败清单会单独列出，需先恢复 Elasticsearch 后重跑。
任一索引失败时命令以非零状态退出，并输出结构化 `pending_index` 清单；使用同一个
`--source-name` 重跑即可继续。

## 首次接管旧数据（authoritative）

只有当输入文件是该来源的**完整权威快照**时，才使用 `--authoritative`。建议先执行：

```powershell
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-2026 --dry-run --authoritative
```

确认快照完整后再正式接管：

```powershell
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-2026 --authoritative
```

该模式会停用本次文件遗漏的同 `source_name` 记录，以及尚无 `source_name` 的旧版展厅和
展品；其他非空来源的数据不受影响。如果一个待停用展厅仍有其他来源的启用展品，该展厅也会
保持启用。权威快照若漏行，会让对应旧数据退出小程序，因此日常增量文件不得使用此参数。

对于待停用的启用展品，导入器必须先成功删除它的旧 RAG source，才会提交数据库 inactive
状态。首次接管还会清理旧初始化脚本按 `document_id` 写入的 document 向量 source，避免这些
占位分片挤占真实数据的检索 top-k；只删除检索索引，不删除 `Document` 或 `IngestionJob`
数据库记录，也不处理没有关联到旧展品的通用馆方文档。任一 source 删除失败时，该展品和
相关展厅恢复原 active 状态，命令以状态码 3 退出，并在 `pending_index` / `failures` 中列出
待处理项。

`--dry-run` 始终不连接 PostgreSQL、Elasticsearch 或 embedding provider，因此只能报告文件内
显式停用行数。权威模式下返回 `authoritative_cleanup_deferred=true`，表示遗漏行和旧版无来源
数据的实际清理数量要到正式执行、读取数据库后才能确定；正式结果中的
`halls_planned_deactivation`、`exhibits_planned_deactivation` 和对应 `*_deactivated` 才包含这些
数据库派生目标。
