# 半坡导览数据审计

更新时间：2026-08-08

## 当前可信边界

- 九个展厅的 `slug`、名称与已确认的大致简介是当前可信展厅数据，并已固化到
  `data/museum_template/halls.csv` 作为可审计的首次导入模板。
- 展品清单、展品说明、地图和实际路线仍需等待馆方真实数据。
- 前向迁移只补缺失展厅、只填充空简介；数据库中已有的非空简介不被覆盖。运行时只读数据库，
  不再从小程序或后端常量回退展厅简介。
- 临展厅一、临展厅二保留各自在数据库中的可信基础简介，并共用同一套动态拼装规则；仅当前启用展品会进入数量、重点、对话上下文和建议条。

## 唯一正式导入流程

正式数据只使用统一 XLSX 或 CSV 双表格式：

```powershell
uv run python scripts/import_museum_data.py .\data\museum_template --source-name banpo-baseline --dry-run
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-2026 --dry-run
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-2026
```

字段、权威同步和回滚规则见 `docs/museum-data-import.md`。旧的 Markdown 解析/API 全量清空脚本已删除；prompt/persona seed 也不再创建或改写展厅。

## 运行时数据来源

- `/api/v1/tour/halls`：只读取九个可信 slug 中的开放展厅名称与简介，并聚合当前启用展品的数量和重点名称。
- `/api/v1/exhibits`：公开列表、详情、筛选和统计只包含“展品启用 + 展厅启用 + 九厅白名单”同时成立的数据；管理查询仍可看到异常或旧数据以便清理。
- 导览 Agent：展厅与展品事实均由后端数据库生成结构化上下文；前端文本不进入 system prompt。
- 小程序：静态文件只保留九厅身份映射和视觉元数据，不保留展厅简介、展品清单或建议条事实。
- 临展厅：上传/导入或启用展品后自动出现，停用/删除后自动移除；两个临展厅严格按各自 `hall` 隔离。

## 仍待馆方提供

- 当前常设展完整展品清单、展签说明、展柜/点位、时代、类别、重要等级与图片授权。
- 临展厅一、临展厅二的当期主题、展品清单与开放周期。
- 馆内平面图、真实空间顺序和参观动线，最好包含坐标或展柜编号。
- 可用于 RAG 的馆方讲解词、研究资料和教育活动文案。

项目框架已经能在导入真实数据后自动驱动展厅页、展品页、同厅对话上下文、建议条与报告；在上述真实数据接入前，不应把历史演示数据当作馆方事实。
