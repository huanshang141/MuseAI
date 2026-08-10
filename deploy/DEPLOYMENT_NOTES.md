# MuseAI 后端部署资产与配置参考

本目录只提供生产运维资产及一次性安装、配置参考，不是日常发布步骤的第二份副本。本仓库不会自动部署。

生产发布的唯一权威流程是 [`docs/miniapp-content-maintenance.md` 第 7 节](../docs/miniapp-content-maintenance.md#7-生产部署和验收)：先备份，再从精确来源 `origin/main` 记录并切换目标 SHA，随后按锁文件同步依赖、执行迁移、通过 systemd 启停并完成健康检查。禁止用无条件 `git pull` 替代精确 SHA 发布，禁止按进程名执行 `pkill`，禁止用 `nohup` 启动生产后端。

资产清单：

| 文件 | 用途 |
| --- | --- |
| `museai-backend.service` | systemd unit，托管 uvicorn 后端进程 |
| `logrotate-museai` | 后端 `logs/*.log` 日志轮转规则 |
| `pg_backup.sh` | PostgreSQL 每日备份脚本 |
| `test_pg_backup.sh` | 不依赖 Docker/PostgreSQL 的备份成功/失败 mock 回归 |
| `nginx.conf` | HTTPS 反代参考配置（已在线上使用，以线上实际为准） |

以下命令均假设代码位于 `/home/ubuntu/MuseAI`，路径不同请先全局替换。

HTTPS 证书约定放在 `/etc/nginx/ssl/museai/`：

- `/etc/nginx/ssl/museai/fullchain.pem`
- `/etc/nginx/ssl/museai/privkey.pem`

上传到 `/tmp` 的证书文件不会自动生效；必须复制到 Nginx 配置读取的路径，并执行 `sudo nginx -t && sudo systemctl reload nginx`。

---

## 0. 发布流程唯一入口

不要从本文件拼接或简化发布命令。每个发布批次都必须完整执行[小程序内容维护指南中的生产部署和验收流程](../docs/miniapp-content-maintenance.md#7-生产部署和验收)，并保留其中的数据库备份、配置备份、目标 SHA、迁移 head 和健康检查证据。本文件后续章节只用于首次安装或维护部署资产。

报告接口 `POST /api/v1/tour/sessions/:id/report` 和 `GET /api/v1/tour/sessions/:id/report` 同时返回 500，且其他 tour/chat/exhibits 接口正常时，优先检查是否漏跑了迁移。当前报告摘要功能需要 `tour_reports.record_summary` 字段；如果数据库仍是旧 schema，ORM 读写报告表会直接触发 500。

## 1. 安装 systemd service

```bash
# 1) 按锁文件同步依赖并确认虚拟环境命令存在
cd /home/ubuntu/MuseAI
UV=/home/ubuntu/.local/bin/uv
test -x "$UV"
"$UV" lock --check
"$UV" sync --frozen
"$UV" pip check --python /home/ubuntu/MuseAI/.venv/bin/python
test -x /home/ubuntu/MuseAI/.venv/bin/alembic
test -x /home/ubuntu/MuseAI/.venv/bin/uvicorn

# 2) 如代码路径不同，编辑 unit 中的 ExecStart / WorkingDirectory / EnvironmentFile
sudo cp /home/ubuntu/MuseAI/deploy/museai-backend.service /etc/systemd/system/

# 3) 先手工确认迁移可执行
cd /home/ubuntu/MuseAI
.venv/bin/alembic upgrade head
.venv/bin/alembic current

# 4) 注册并启动
sudo systemctl daemon-reload
sudo systemctl enable --now museai-backend
```

注意：

- 若首次接管时仍存在历史手动进程，先核对其完整命令行、父进程、启动时间、工作目录和 `127.0.0.1:8000` 监听归属；只停止已确认属于本项目的精确 PID，再安装 systemd unit。不得按进程名批量停止，也不得保留第二个手动启动实例。
- `EnvironmentFile` 指向 `/home/ubuntu/MuseAI/.env`。systemd 对该文件解析较严格：值含空格必须加引号、不能有 `export`。应用本身也会通过 pydantic-settings 读取同一份 `.env`，两者保持一致即可。
- `uv.lock` 必须由 Git 跟踪。`"$UV" lock --check` 失败或 `"$UV" pip check` 报缺包时禁止重启服务；不要让服务器保留一个覆盖仓库状态的未跟踪旧锁文件。
- unit 直接调用当前 checkout 的 `.venv/bin/alembic` 与 `.venv/bin/uvicorn`，避免长期运行的 `uv run` 父进程与后续 `uv run` 运维命令发生环境锁等待；因此每次切换提交后必须先用绝对路径执行 `"$UV" sync --frozen`。
- unit 会在启动前执行 `.venv/bin/alembic upgrade head`。没有待执行 revision 时该命令是幂等的；如果迁移失败，服务不会在错误 schema 上启动。
- 不要给生产 unit 加 `--reload`。
- `docker-compose.yml` 不再提供数据库弱口令。首次创建或重建基础容器前，必须在未纳入 Git 的 `.env` 中设置 `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`，且密码与 `DATABASE_URL` 一致；先用 `docker compose config --quiet` 校验，再执行 `docker compose up -d`。
- PostgreSQL、Redis、Elasticsearch 都使用 `restart: unless-stopped`，由 Docker 在主机重启后恢复；systemd 后端仍通过 `/api/v1/ready` 等待并验证依赖，不能只以进程 `active` 判断可用。

## 2. 日常操作

```bash
sudo systemctl status museai-backend --no-pager -l   # 状态
sudo systemctl restart museai-backend                # 重启（改 .env 后必须执行）
sudo systemctl stop museai-backend                   # 停止
journalctl -u museai-backend -n 100 --no-pager       # 最近日志
journalctl -u museai-backend -f                      # 跟踪日志
```

修改 unit 文件本身后需要：`sudo systemctl daemon-reload && sudo systemctl restart museai-backend`。

## 3. 配置 logrotate

```bash
sudo cp /home/ubuntu/MuseAI/deploy/logrotate-museai /etc/logrotate.d/museai
sudo logrotate --debug /etc/logrotate.d/museai    # 干跑校验，不实际轮转
sudo logrotate --force /etc/logrotate.d/museai    # 可选：立即执行一次验证
```

策略：每日轮转、保留 14 天、压缩、`copytruncate`（后端持有日志文件句柄，不支持信号重开）。
Nginx 自带 `/etc/logrotate.d/nginx`，确认存在即可，无需重复配置。

## 4. 配置每日数据库备份

```bash
set -euo pipefail
sudo mkdir -p /var/backups/museai
sudo chown ubuntu:ubuntu /var/backups/museai

# Compose 固定使用容器 museai-postgres、数据库角色 museai：
docker ps --format '{{.Names}}' | grep -Fx museai-postgres
BACKUP_FILE="$(PG_CONTAINER=museai-postgres PGUSER=museai DB_NAME=museai BACKUP_DIR=/var/backups/museai bash /home/ubuntu/MuseAI/deploy/pg_backup.sh)"
gzip -t "$BACKUP_FILE"
sha256sum "$BACKUP_FILE"
```

成功后添加 cron（每日 03:30）：

```bash
crontab -e
# 添加一行：
30 3 * * * PG_CONTAINER=museai-postgres PGUSER=museai DB_NAME=museai BACKUP_DIR=/var/backups/museai bash /home/ubuntu/MuseAI/deploy/pg_backup.sh >> /var/backups/museai/backup.log 2>&1
```

脚本默认保留 7 天（`RETENTION_DAYS` 可调），不在任何位置硬编码密码。容器分支未显式传 `PGUSER` 时也默认 `museai`，但运维命令仍必须显式传入，避免复制到不同 Compose 环境后产生歧义。

**上线前必须执行下列完整恢复演练**。它只创建带随机后缀的临时库；只有本流程成功创建的库才会由 trap 删除，绝不连接或删除生产 `museai`：

```bash
set -euo pipefail
PG_CONTAINER=museai-postgres
PGUSER=museai
BACKUP_FILE="${BACKUP_FILE:?set BACKUP_FILE to an absolute museai_*.sql.gz path}"
test -f "$BACKUP_FILE"
test ! -L "$BACKUP_FILE"
gzip -t "$BACKUP_FILE"
BACKUP_SHA256="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"

RESTORE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RESTORE_DB="museai_restore_test_${RESTORE_STAMP//[^A-Za-z0-9_]/_}_$$"
case "$RESTORE_DB" in
    museai_restore_test_*) ;;
    *) printf 'unsafe restore database name: %s\n' "$RESTORE_DB" >&2; exit 1 ;;
esac
RESTORE_CREATED=false
cleanup_restore_db() {
    if [ "$RESTORE_CREATED" = true ]; then
        docker exec "$PG_CONTAINER" dropdb --if-exists -U "$PGUSER" "$RESTORE_DB" >/dev/null
    fi
}
trap cleanup_restore_db EXIT

RESTORE_DB_EXISTS="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname = '$RESTORE_DB'")"
test -z "$RESTORE_DB_EXISTS"
docker exec "$PG_CONTAINER" createdb -U "$PGUSER" "$RESTORE_DB"
RESTORE_CREATED=true
gzip -dc "$BACKUP_FILE" | docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$RESTORE_DB"
RESTORE_SCHEMA_OK="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$RESTORE_DB" -Atqc "SELECT (to_regclass('public.alembic_version') IS NOT NULL AND to_regclass('public.halls') IS NOT NULL)::text")"
test "$RESTORE_SCHEMA_OK" = t
RESTORED_REVISION="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$RESTORE_DB" -Atqc 'SELECT version_num FROM alembic_version LIMIT 1')"
test -n "$RESTORED_REVISION"
docker exec "$PG_CONTAINER" dropdb -U "$PGUSER" "$RESTORE_DB"
RESTORE_CREATED=false
trap - EXIT
printf 'restore drill passed: backup=%s sha256=%s revision=%s\n' "$BACKUP_FILE" "$BACKUP_SHA256" "$RESTORED_REVISION"
```

任一 `gzip`、创建、恢复、schema 查询或临时库删除失败都会非零停止。只有最后出现 `restore drill passed` 才能把该备份视为可恢复。生产库和图片回退的保留旧状态、候选库验证及安全 tar 校验命令见[内容维护指南第 8 节](../docs/miniapp-content-maintenance.md#8-回退)。

## 5. 验证 health 与 readiness

`/api/v1/health` 只检查应用进程存活，不能作为发布成功依据；`/api/v1/ready` 会检查 PostgreSQL、Redis 和 Elasticsearch，是启停、发布和回退的权威门禁。

```bash
set -euo pipefail
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ready
curl -fsS https://api.banpo-museai.xyz/api/v1/health
curl -fsS https://api.banpo-museai.xyz/api/v1/ready
PORT_8000_LISTENERS="$(sudo ss -H -lnt '( sport = :8000 )')"
test -n "$PORT_8000_LISTENERS"
```

重启服务器后再验证一轮，确认 `enable` 生效（开机自启）。

## 6. 确认旧 3000 端口保持关闭

当前唯一权威链路是 systemd 监听 `127.0.0.1:8000`，由 Nginx 提供 `https://api.banpo-museai.xyz`；3000 不是发布、readiness 或调试回退的必要条件，不应保留本机监听、Docker 映射或公网入站规则。

1. 腾讯云控制台 → 轻量应用服务器 → 防火墙：确认不存在 3000 端口入站规则。
2. Compose 或历史启动参数中不得存在 `0.0.0.0:3000->8000` 或 `127.0.0.1:3000->8000` 映射。
3. 用 fail-closed 检查确认本机无监听、公网端口不可访问、HTTPS readiness 正常：

   ```bash
   set -euo pipefail
   PORT_3000_LISTENERS="$(sudo ss -H -lnt '( sport = :3000 )')"
   test -z "$PORT_3000_LISTENERS"
   if curl --connect-timeout 3 --max-time 5 -fsS http://122.152.232.190:3000/api/v1/health >/dev/null 2>&1; then
       printf 'legacy public port 3000 is still reachable\n' >&2
       exit 1
   fi
   curl -fsS https://api.banpo-museai.xyz/api/v1/ready
   ```

4. 同时确认 5432/6379/9200（PostgreSQL/Redis/Elasticsearch）均未对公网开放。

## 7. 安全提醒

- `.env`、证书私钥、数据库密码永远不进 Git。
- 改完 `.env` 后 `sudo systemctl restart museai-backend` 才生效。
- 曾在聊天、截图或日志中出现过的 AppSecret / LLM key / TTS key，上线前必须轮换。
