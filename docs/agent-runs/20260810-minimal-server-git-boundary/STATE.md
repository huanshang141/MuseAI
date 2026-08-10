# 2026-08-10 服务器直拉部署与 Git 边界整理

## 目标

- 保留 `/home/ubuntu/MuseAI` 作为服务器直接拉取精确提交并部署的工作树。
- 不实施 `/srv/museai` 等大规模路径迁移，不移动 Docker 数据卷。
- 扩充 `.gitignore`，阻止密钥、证书、数据库、转储、上传文件和运行产物误入 Git。
- 清理确定无引用、已被错误跟踪的生成物；真实展厅和展品 CSV 继续版本化。

## 已确认事实

- 本地后端分支与远端同步，开始时工作树干净。
- 服务器当前运行路径仍是 `/home/ubuntu/MuseAI`，生产服务、`.env`、`.venv` 和日志均引用该目录。
- 证书由 `/etc/nginx/ssl` 或 `/etc/letsencrypt` 管理；PostgreSQL、Redis、Elasticsearch 数据由 `/var/lib/docker` 命名卷管理。
- 展品上传图片、数据库/图片备份、应用日志和 `.env` 是服务器本地持久内容，不应提交。
- `data/museum_template` 与 `data/museum_test_data` 是版本化导入输入，应继续提交；未来真实数据使用同一受校验格式进入版本控制。
- `test_alembic.db` 是被 Git 跟踪的 SQLite 生成物，仓库没有代码或文档引用；现有 ignore 规则无法自动取消其跟踪。
- 独立审计确认 508 个 tracked 文件中只有 `test_alembic.db` 是明确误跟踪生成物；`frontend/package-lock.json` 和四个 museum CSV 必须保留。
- 已接受最小部署结构：不创建 `/srv/museai` 等新运行根，服务器继续直接获取精确 SHA。
- `.gitignore` 已收窄容易误伤 lockfile、公共参考资料和源码目录的规则，并补齐服务器本地凭证与运行产物规则。
- `docs/server-storage-layout.md` 已改写为直接 checkout 与持久内容边界；`test_alembic.db` 已从工作树和 Git 索引删除。
- 权威部署文档已增加目标 tree 受保护路径预检和 `git switch --no-overwrite-ignore`；依赖同步/迁移仍严格位于后端停止之后。
- 定向配置/迁移回归 `27 passed`，`uv lock --check`、`uv pip check`、scoped Ruff 和 ignore 契约通过。
- 后端全量 `1590 passed, 23 skipped, 9 warnings`，无失败。
- 14 个 Bash 文档块与 2 个部署脚本语法通过；首次 WSL 启动器的中文网络提示存在终端编码噪声，随后改用 Git Bash 严格复核，文档 UTF-8 内容本身无损坏。
- 正式模板 dry-run 验证 9 厅/0 展品，联调数据 dry-run 验证 9 厅/46 展品；两者均为 `validated`，未连接生产依赖。
- 最终独立复查未发现 P0/P1；目标 tree 门禁同时覆盖受保护根路径本身和其子路径，避免目录名被强制提交为符号链接时漏检。
- 边界提交 `875f5db9dd74a9676e296398fcc821dc10ee764f` 已推送到 `origin/codex/data-driven-miniapp-framework`，服务器已 detached checkout 同一精确 SHA，工作树干净。
- 本批次没有运行时代码或依赖变化，因此未重启后端；同步前后 MainPID 相同，`.env` 哈希未变化，内网与公网 readiness 均 healthy。
- 服务器根目录 85 字节的旧 `package-lock.json` 没有对应根 `package.json`、未被进程打开；已备份到 `/home/ubuntu/museai-config-backups/stale-root-package-lock_20260810T154408Z.json` 后从 checkout 删除。执行记录为 `/home/ubuntu/museai-config-backups/repository_boundary_20260810T154408Z.env`。

## 完成状态

1. 本地提交、origin 推送和服务器精确 SHA 同步已完成。
2. 仓库、服务持久内容和后续真实数据更新边界已写入权威维护文档。

## 安全边界

- 不读取或输出 `.env`、私钥、证书正文、数据库卷或备份正文。
- 不执行 `git clean -fdx`；它会删除服务器所需的 `.env`、`.venv` 和日志。
- 未确认的旧备份、构建依赖和缓存不在本批次删除。
