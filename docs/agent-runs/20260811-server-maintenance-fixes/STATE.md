# 2026-08-11 服务器维护问题收口

## 边界

- 仅处理服务器审计已列出的六项：日志轮转、无效旧备份、仓库根旧日志与 pytest 缓存、证书目录判定、发布记录最终 SHA、Swap。
- 后端仓库：`E:\Proj\Museum_agent\MuseAI\backend`，分支 `main`。
- 生产 checkout：`/home/ubuntu/MuseAI`；不修改小程序或管理端功能。
- 证书、备份和系统配置先验证引用与回退路径，不做未经验证的删除。

## 已验证事实

- 本地 `main`、`origin/main` 与生产运行 checkout 均为 `63f6e75599a0d24a844388365289f6c99752ff1a`，本地工作树在本检查点创建前干净。
- 后端由系统级 `museai-backend.service` 托管；服务 active/running，内外网 readiness 正常。
- 应用五类日志已由 Loguru 每日轮转并保留 7 天；`deploy/logrotate-museai` 会二次轮转，属于应删除的过时资产。
- 截图中的六项来自此前服务器只读审计；本轮必须重新以实时状态核验。
- 两套证书目录都在使用：API 使用 `/etc/nginx/ssl/museai`，官网使用 `/etc/letsencrypt`；只能归档其中未被引用的旧手工网站证书。
- 20 B 旧备份是空 gzip 流且无引用；另 8 个数据库备份有效。现无 MuseAI 定时备份任务。
- `backend_uvicorn.log` 与 `.pytest_cache` 均未跟踪、已忽略、无打开句柄。
- `/swapfile` 已存在且是完整的 2 GiB Linux swap，只是未启用、未写入 `/etc/fstab`；当前 `vm.swappiness=60`。
- 当前发布记录有 `TARGET_SHA` 与纯文档 `DOCUMENTATION_SHA`，缺少统一的 `FINAL_SHA`。

## 本轮变更

- 已创建 PostgreSQL backup service/timer 和 Swap sysctl 模板；备份脚本固定 `0700/0600` 权限。
- 已删除过时的 MuseAI Logrotate 资产，并修正日志、证书路径、存储边界和发布记录文档。
- 本地备份 mock、脚本语法、24 个文档 Bash 块通过；当前候选 service/timer 字节已由生产服务器 systemd 249 执行 `systemd-analyze verify` 通过。
- 尚未修改生产配置、清理生产文件或切换生产 checkout。

## 验证要求

- 每项修复必须有对应 dry-run、引用检查或状态验证。
- 结束前复核 systemd、Nginx 配置、数据库/缓存/检索 readiness、Swap、Git 与发布记录。

## 唯一下一步

- 等待当前仓库 diff 的独立复核；通过后更新 changelog、提交并推送 `main`，再按精确 SHA 实施服务器修复。
