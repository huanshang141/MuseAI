# 服务器测试数据与部署检查点

- 目标：把生产库 46 条旧展品整理为明确标注的测试 CSV，分配到九个可信展厅；仅保留 `test@test.com` 管理员；完成迁移、导入和多轮验证。
- 本地后端：`codex/data-driven-miniapp-framework`，提交 `1eee2e13f341328114dd4265070c5810135a76b9`，开始时工作树干净。
- 服务器：`/home/ubuntu/MuseAI` 检出同一提交；运行进程仍为旧部署，数据库迁移停在 `20260716_report_summary_hash`。
- 回退基线：`/home/ubuntu/museai-backups/museai_20260808_161354.sql.gz`，SHA-256 `38ae4407b6a83077d53b93c00b891b50582ef7fb5ae383f78bc38f3903f04c57`。
- 已确认：九个展厅可信；46 条旧展品均为无来源记录且集中在 `basic-exhibition-hall`；管理员为 `admin@museai.local` 与 `test@test.com` 两个。
- 数据约定：测试记录必须在名称、介绍和来源中显式标明测试性质；使用稳定来源 `banpo-museum-data`，后续真实权威快照沿用该来源即可停用遗漏的测试记录。
- 资源约束：2C8G；Elasticsearch 容器约 713 MiB/768 MiB，导入与索引串行执行。

## 下一批

1. 已完成：导出旧展品并生成 `data/museum_test_data/{halls,exhibits}.csv`；46 条记录覆盖九厅，名称和介绍均显式标记测试。
2. 已完成：CSV 双 dry-run、导入专项 33 项、迁移专项 4 项、全后端 `1156 passed, 23 skipped, 10 warnings`；依赖与差异检查通过。
3. 已完成：提交 `6a3720e`；本机到 GitHub 443 连续超时，改用已双端校验的 Git bundle 同步服务器，origin 尚待网络恢复后补推。
4. 已完成：部署前备份、迁移、管理员角色收敛、服务重启和权威导入；`test@test.com` 为唯一管理员。
5. 已完成：数据库、ES、公开 API、30 条同厅恢复、OCC 冲突、SSE、报告归纳与双次有效 WAV 实测通过。
6. 待完成：提交本次部署审计文档，并在 GitHub 连通恢复后推送后端分支。
