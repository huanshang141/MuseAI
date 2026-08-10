# 2026-08-11 服务器维护问题收口

## 边界

- 仅处理服务器审计列出的六项：日志轮转、无效旧备份、仓库根旧日志与 pytest 缓存、证书目录判定、发布记录最终 SHA、Swap。
- 后端仓库为 `E:\Proj\Museum_agent\MuseAI\backend` 的 `main`；生产 checkout 为 `/home/ubuntu/MuseAI`。小程序和管理端功能未改。
- 所有服务器文件变更先验证引用并保留回退副本；未删除任何仍被 Nginx 或服务引用的证书和数据。

## 已完成变更

- 运行目标 `544e93786b8e2f61cb602a044df1009a1da823da` 已部署；应用由 systemd 托管，未用 `nohup` 或按进程名启停。
- 应用五类日志继续由 Loguru 每日轮转并保留 7 天；删除会造成二次轮转的仓库旧规则，不创建 `/etc/logrotate.d/museai`。长期无新事件的 `auth.log`、`document.log` 虽修改时间较早，但仍是当前进程打开的活动文件，不属于过期轮转文件。
- 每日 03:30 的 PostgreSQL systemd timer 已 enabled/active；备份目录和文件权限分别固定为 `0700/0600`。最新备份已恢复到临时库，关键表与迁移 `20260809_trusted_hall_chat_history` 验证通过，临时库残留为 0。
- 20 B 空 gzip 旧备份已隔离，旧 `backend_uvicorn.log` 已压缩归档，`.pytest_cache` 已清理；原路径均不存在。
- API 手工证书与官网 Let’s Encrypt 证书均在用，因此保留两套活动目录；只归档未引用的旧手工官网证书。API 证书与私钥权限为 `root:root 0644/0600`，磁盘指纹与公网指纹一致。
- snap Certbot 续期 dry-run 成功并保持 timer enabled/active；重复的 apt timer 已 disabled/inactive，未卸载软件包。
- 现有 2 GiB `/swapfile` 已启用并仅写入一条 `fstab` 记录，`vm.swappiness=10`。
- 生产回退资产和操作证据位于 `/home/ubuntu/museai-config-backups/maintenance_20260810T173754Z`；本批次发布记录使用 `TARGET_SHA`、`DOCUMENTATION_SHA` 和 `FINAL_SHA` 区分运行目标与最终文档 checkout。

## 验证

- 本地：备份 mock、25 个相关 Markdown Bash 块、候选 systemd service/timer、配置/日志定向 pytest、Ruff/差异检查和 staged secret scan 均通过。
- 生产：后端与 Nginx active，后端 NRestarts=0；loopback readiness、公网 readiness 和官网均为 HTTP 200，发布后 error journal 为 0。
- 生产：备份 timer enabled/active 且手动执行成功；恢复演练通过；Swap、`fstab`、证书指纹/权限、Certbot timers、归档路径和干净 Git 工作树联合终检通过。

## 唯一下一步

- 无。本任务六项均已收口。后续独立维护事项是 API 手工证书在 2026-12-21 到期前更新，建议不晚于 2026-11-21 执行。
