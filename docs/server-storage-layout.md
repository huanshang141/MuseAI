# MuseAI 服务器存储重排方案

## 范围与原则

本方案基于 2026-08-10 对 `122.152.232.190` 的只读盘点。当前磁盘并未告急：系统盘约 99 GiB，已用约 22 GiB；重排目标是分离发布代码、配置、运行数据、日志和备份，而不是立即腾空间。

- 未经单独审批，不移动或删除当前运行目录、Docker 卷、有效备份或认证工具目录。
- 先复制和验证，再切换引用；源目录至少保留 7 天作为回退。
- 微信小程序是独立仓库，不部署在服务器；`/home/ubuntu/MuseAI/frontend` 是管理端源码。
- Docker 数据继续由 `/var/lib/docker` 管理，禁止手工移动卷内容或执行 `down -v`。

## 当前依赖

- systemd 工作目录：`/home/ubuntu/MuseAI`。
- 后端启动程序：`/home/ubuntu/MuseAI/.venv/bin/uvicorn`。
- 当前 unit 的 `ExecStartPre` 还会从旧 `.venv` 自动执行 `alembic upgrade head`；目标布局必须把迁移移回带备份记录的显式发布阶段。
- 运行配置：`/home/ubuntu/MuseAI/.env`。
- 应用日志：`/home/ubuntu/MuseAI/logs`。
- Python 运行时还依赖 `/home/ubuntu/.local/share/uv/python`，因此 `.venv` 不能脱离该运行时单独搬迁。
- Compose 配置：`/home/ubuntu/MuseAI/docker-compose.yml`；PostgreSQL、Elasticsearch、Redis 数据在 Docker 命名卷中。
- Nginx 管理端根目录：`/var/www/museai-admin`；它与仓库 `frontend/dist` 当前文件清单、大小、时间戳和元数据指纹一致，但只有前者是线上目录，本轮未以逐文件内容哈希替代部署验收。
- 展品图片：`/home/ubuntu/museai-data/exhibit-images`，当前为空。
- 数据库、图片及配置备份分别散落在 `/home/ubuntu/museai-backups` 和 `/home/ubuntu/museai-config-backups`。

## 目标布局

```text
/srv/museai/
├── repository.git/                    # 受控 bare 仓库，只 fetch 精确后端分支
├── releases/
│   └── <UTC时间>-<Git SHA>/
├── current -> releases/<当前版本>
└── infra/
    ├── docker-compose.yml
    ├── docker/
    └── nginx/museai-admin-ip.conf

/opt/museai/python/<明确版本>/         # release venv 绑定不可变版本路径
/opt/museai/python/current -> <明确版本>
/etc/museai/backend.env                # 后端应用配置
/etc/museai/compose.env                # Compose 所需数据库变量
/var/lib/museai/exhibit-images/        # 持久图片
/var/log/museai/app/                   # 应用日志
/var/log/museai/backup.log

/var/backups/museai/
├── database/
├── images/
├── config/
├── manifests/
└── legacy/

/var/www/museai-admin/
├── releases/<Git SHA>/
└── current -> releases/<当前版本>
```

## 分阶段迁移

### 0. 冻结回退基线

无需停机。记录 Git SHA、systemd/Nginx 配置哈希、Compose 项目名、容器和卷名；新建迁移前数据库、图片与配置备份，验证 SHA-256。当前目录保持不动。

### 1. 创建并复制目标目录

无需停机。创建目标目录和权限；在 `/opt/museai/python/<明确版本>` 安装固定 Python，为新 release 重建虚拟环境。release 只能来自以下一种受控来源：

- `/srv/museai/repository.git` 对 `origin/codex/data-driven-miniapp-framework` 精确 SHA 创建的 detached worktree；或
- 已验证 SHA-256、只包含 Git 跟踪文件的发布制品。

禁止把当前工作目录整体 rsync 为 release；`.env`、现有完整 `.git` 目录、旧 `.venv`、日志、缓存、测试临时目录和管理端 `node_modules` 都不得复制进新 release。使用 Git worktree 时只保留 Git 自动生成的 worktree 控制文件。需要复制的非代码资产只能按明确 allowlist 处理。新 release 先完成依赖检查、迁移预检和应用导入；无 schema 变更时可临时监听 `127.0.0.1:8001` 做候选 readiness，不能抢占生产 8000。涉及迁移时，先在临时恢复数据库演练，生产数据库只在切换窗口执行迁移。

目标权限应在切换前固定：release 代码由部署账号拥有、运行时只读；`backend.env` 与 `compose.env` 使用 `root:root 0600`，读取它们的部署和 Compose 命令统一经 `sudo`；日志和图片目录由后端服务用户可写；备份目录为 `0700`、备份文件为 `0600`；管理端静态文件对 `www-data` 只读。`backend.env` 必须显式设置 `LOG_DIR=/var/log/museai/app` 和 `EXHIBIT_IMAGE_DIR=/var/lib/museai/exhibit-images`，不能继续依赖 release 下的相对默认路径。

### 2. 切换后端

预计停机 5–30 秒。目标 systemd unit 改为：

- `WorkingDirectory=/srv/museai/current`
- `ExecStart=/srv/museai/current/.venv/bin/uvicorn ...`
- `EnvironmentFile=/etc/museai/backend.env`
- 日志目录 `/var/log/museai/app`
- 图片目录 `/var/lib/museai/exhibit-images`

目标 unit 不再保留自动 `ExecStartPre=... alembic upgrade head`。迁移必须属于“已验证备份和发布记录→停止旧服务→原子切换 `current`→使用新 release 显式执行 `alembic upgrade head`→成功后启动服务”的受控发布阶段；迁移失败时服务保持停止，普通重启、改 env 或机器启动不能在无备份上下文中自动迁移数据库。同一迁移批次还要更新仓库中的 `deploy/museai-backend.service` 和权威发布/回退文档，避免线上 unit 与版本化流程再次漂移。

由于 `/etc/museai/backend.env` 为 `root:root 0600`，显式迁移不能依赖部署账号直接读取该文件，也不能仅以 `sudo alembic ...` 假定环境变量会自动注入。目标方案需提供一个版本化的 `Type=oneshot` 迁移 unit：它与后端 unit 使用相同的 `WorkingDirectory=/srv/museai/current`、`EnvironmentFile=/etc/museai/backend.env`、服务用户和新 release 虚拟环境；发布程序通过 `sudo systemctl start museai-migrate.service` 执行，并检查 unit 退出状态与 journal。该 unit 只允许在已完成备份且后端停止的发布窗口手动启动，不设置 `WantedBy`、timer 或后端依赖关系。

切换前执行 `systemd-analyze verify`，随后 `daemon-reload` 并按上述顺序停服、迁移、启动；最后验证内网、公网 readiness、报告和图片读写。正常切换预计 5–30 秒，但维护窗口需为 systemd 20 秒停止宽限、Alembic 和回退预留 2–5 分钟。回退时恢复旧 service/env，或将 `current` 指回上一 release；若迁移不向后兼容，还必须恢复迁移前数据库。

### 3. 切换管理端静态发布

通常无需停机。管理端在 CI 或本地构建，服务器只接收 `dist`；上传到 `/var/www/museai-admin/releases/<SHA>` 后原子更新 `current`。实际管理端站点配置位于 `/etc/nginx/conf.d/museai-admin-ip.conf`，先把其去敏模板纳入 `/srv/museai/infra/nginx/museai-admin-ip.conf` 管理，再将线上 root 改为 `/var/www/museai-admin/current`；通过 `nginx -t` 后 reload。回退只切换符号链接。

### 4. 分离 Compose 配置

安排独立维护窗口。把 Compose 文件复制到 `/srv/museai/infra`；所有检查与操作显式使用 `docker compose -p museai --env-file /etc/museai/compose.env -f /srv/museai/infra/docker-compose.yml ...`，避免缺少 `POSTGRES_PASSWORD` 或改变项目名。先比较 `docker compose config` 输出，并确认继续引用现有三个 `museai_*_data` 命名卷。旧工作目录标签只是元数据，不为改标签主动重建健康容器；等真实配置或镜像升级时再从新路径重建。维护窗口预留 5–10 分钟，并以 PostgreSQL、Elasticsearch、Redis 全部重新 healthy 为结束条件。

### 5. 统一备份与自动化

把旧备份先复制到 `legacy`；新备份分别进入 `database/images/config/manifests`。当前服务器没有 MuseAI timer 或 cron，这一步属于新增自动化。数据库备份脚本必须显式传入 `BACKUP_DIR=/var/backups/museai/database`；现有按天清理逻辑不能直接实现“14 个日备份 + 8 个周备份”，周备份需另行设计并测试。建议采用 systemd timer，并增加异机或对象存储副本。必须完成一次临时数据库恢复测试，才能淘汰旧目录。

### 6. 观察后清理

新路径稳定至少 7 天，且代码回退、数据库恢复和管理端回退均演练成功后，再单独审批删除源目录和旧缓存。

## 清理候选与优先级

高收益但需要专门确认：

- `~/.vscode-server/cli/servers` 约 3.70 GiB：当前仍有 VS Code Agent，需先断开远程会话，通过 VS Code Remote 的官方清理方式识别并移除未使用版本，不能按目录时间直接删除。
- Docker build cache 报告约 1.47 GiB 可回收：仅使用 Docker 自身 prune 命令，不手工删除 `/var/lib/docker`；因层共享，实际释放量可能更少。
- systemd journal 约 1.2 GiB：先配置例如 `SystemMaxUse=512M` 和保留期，再受控 vacuum。

中等收益：

- 管理端 `frontend/node_modules` 约 238 MiB：管理端切换为离线/CI 构建并验证 lockfile 可重建后删除。
- npm cache 约 264 MiB、NVM 约 455 MiB：先确认服务器不再承担管理端构建。
- uv cache 逻辑大小约 586 MiB：使用 `uv cache prune`，不要手工删除可能与虚拟环境硬链接的文件。

小型候选：旧 `backend_uvicorn.log`、20 字节失败数据库备份、`/tmp/museai*` 探针、测试缓存和旧字节码。它们收益很小，放在迁移成功后的独立清理批次。

## 明确保留

- 当前 `/home/ubuntu/MuseAI`、`.venv`、`.env` 和运行日志，直至新布局稳定并验证回退。
- 所有 Docker 命名卷和有效数据库、图片、配置、发布备份。
- `/var/www/museai-admin` 当前线上静态文件。
- `.ssh`、`.codex`、`.claude` 等认证或工作工具目录。
- `/home/ubuntu/deploy-logs` 中属于其他项目的内容。
