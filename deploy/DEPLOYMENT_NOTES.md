# MuseAI 后端部署资产与配置参考

本目录只提供生产运维资产及一次性安装、配置参考，不是日常发布步骤的第二份副本。本仓库不会自动部署。

生产发布的唯一权威流程是 [`docs/miniapp-content-maintenance.md` 第 7 节](../docs/miniapp-content-maintenance.md#7-生产部署和验收)：先备份，再从精确来源 `origin/main` 记录并切换目标 SHA，随后按锁文件同步依赖、执行迁移、通过 systemd 启停并完成健康检查。禁止用无条件 `git pull` 替代精确 SHA 发布，禁止按进程名执行 `pkill`，禁止用 `nohup` 启动生产后端。

资产清单：

| 文件 | 用途 |
| --- | --- |
| `museai-backend.service` | systemd unit，托管 uvicorn 后端进程 |
| `pg_backup.sh` | PostgreSQL 每日备份脚本 |
| `test_pg_backup.sh` | 不依赖 Docker/PostgreSQL 的备份成功/失败 mock 回归 |
| `museai-backup.service` / `museai-backup.timer` | 每日 03:30 执行原子数据库备份 |
| `museai-swap.conf` | 2 GiB Swap 缓冲的低换页倾向配置 |
| `nginx.conf` | HTTPS 反代参考配置（已在线上使用，以线上实际为准） |

以下命令均假设代码位于 `/home/ubuntu/MuseAI`，路径不同请先全局替换。

当前两个 HTTPS 站点使用不同证书来源：

- API：`/etc/nginx/ssl/museai/api.banpo-museai.xyz_bundle.crt` 与同目录 `.key`。
- 官网：`/etc/letsencrypt/live/banpo-museai.xyz/fullchain.pem` 与 `privkey.pem`。

两套目录都被生效的 Nginx server block 引用，不能因为并存而合并或删除。上传到 `/tmp` 的证书不会自动生效；替换前必须从 `sudo nginx -T` 核对当前引用，替换后执行 `sudo nginx -t && sudo systemctl reload nginx`。

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

## 3. 验证日志保留与证书职责

```bash
set -euo pipefail
cd /home/ubuntu/MuseAI
test ! -e /etc/logrotate.d/museai
test -f /etc/logrotate.d/nginx
find logs -maxdepth 1 -type f -name '*.log' -printf '%f %s bytes %TY-%Tm-%Td %TH:%TM\n' | sort
sudo nginx -T 2>/dev/null | grep -E 'server_name|ssl_certificate(_key)?'
```

应用的五类 `logs/*.log` 由 Loguru 自身每日轮转并保留 7 天。不要安装 MuseAI 专用 Logrotate，否则活动文件和 Loguru 已轮转文件会被二次处理。Nginx 继续使用系统自带的 `/etc/logrotate.d/nginx`。

API 手工证书与官网 Certbot 证书必须分别维护。官网只保留一套已验证的 Certbot renewal timer；切换 timer 前先用保留的 Certbot 执行 `renew --dry-run`。API 手工证书不受 Certbot 管理，必须在到期前单独替换，并核对公网证书指纹。

## 4. 配置每日数据库备份

```bash
set -euo pipefail
sudo install -d -o ubuntu -g ubuntu -m 0700 /home/ubuntu/museai-backups
sudo install -o root -g root -m 0644 /home/ubuntu/MuseAI/deploy/museai-backup.service /etc/systemd/system/museai-backup.service
sudo install -o root -g root -m 0644 /home/ubuntu/MuseAI/deploy/museai-backup.timer /etc/systemd/system/museai-backup.timer
sudo systemd-analyze verify /etc/systemd/system/museai-backup.service /etc/systemd/system/museai-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now museai-backup.timer
sudo systemctl start museai-backup.service
sudo systemctl is-enabled --quiet museai-backup.timer
sudo systemctl is-active --quiet museai-backup.timer
sudo systemctl list-timers museai-backup.timer --no-pager
```

手工运行成功后选择最新备份并校验；脚本固定目录权限为 `0700`、文件权限为 `0600`，默认保留 7 天：

```bash
set -euo pipefail
BACKUP_FILE="$(find /home/ubuntu/museai-backups -maxdepth 1 -type f -name 'museai_*.sql.gz' -printf '%T@ %p\n' | sort -nr | awk 'NR == 1 {print $2}')"
test -n "$BACKUP_FILE"
test "$(stat -c '%a' /home/ubuntu/museai-backups)" = 700
test "$(stat -c '%a' "$BACKUP_FILE")" = 600
gzip -t "$BACKUP_FILE"
test -n "$(gzip -dc "$BACKUP_FILE" | tail -n 20)"
sha256sum "$BACKUP_FILE"
```

定时器使用 Compose 容器 `museai-postgres`、数据库角色和库名 `museai`，不硬编码密码。漏过的执行会由 `Persistent=true` 在开机后补跑；如果 Docker 已启动但 PostgreSQL 容器仍在恢复，oneshot 会以 60 秒间隔有限重试，失败从 `systemctl status museai-backup.service` 和 journal 查看。

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
test "$RESTORE_SCHEMA_OK" = true
RESTORED_REVISION="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$RESTORE_DB" -Atqc 'SELECT version_num FROM alembic_version LIMIT 1')"
test -n "$RESTORED_REVISION"
docker exec "$PG_CONTAINER" dropdb -U "$PGUSER" "$RESTORE_DB"
RESTORE_CREATED=false
trap - EXIT
printf 'restore drill passed: backup=%s sha256=%s revision=%s\n' "$BACKUP_FILE" "$BACKUP_SHA256" "$RESTORED_REVISION"
```

任一 `gzip`、创建、恢复、schema 查询或临时库删除失败都会非零停止。只有最后出现 `restore drill passed` 才能把该备份视为可恢复。生产库和图片回退的保留旧状态、候选库验证及安全 tar 校验命令见[内容维护指南第 9 节](../docs/miniapp-content-maintenance.md#9-回退)。

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

## 7. 启用现有 2 GiB Swap 缓冲

只复用已经初始化为 Linux swap、权限为 `0600` 的 `/swapfile`；文件不存在或类型不对时停止，不在上线窗口临时创建：

```bash
set -euo pipefail
test -f /swapfile
test ! -L /swapfile
test "$(stat -c '%U:%G:%a:%s' /swapfile)" = 'root:root:600:2147483648'
test "$(sudo blkid -p -s TYPE -o value /swapfile)" = swap
if ! swapon --noheadings --show=NAME | grep -Fx /swapfile >/dev/null; then
    sudo swapon /swapfile
fi
if ! grep -Eq '^[[:space:]]*/swapfile[[:space:]]+none[[:space:]]+swap[[:space:]]+sw[[:space:]]+0[[:space:]]+0([[:space:]]*#.*)?$' /etc/fstab; then
    printf '%s\n' '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo install -o root -g root -m 0644 /home/ubuntu/MuseAI/deploy/museai-swap.conf /etc/sysctl.d/99-museai-swap.conf
sudo sysctl --system >/dev/null
test "$(sysctl -n vm.swappiness)" = 10
swapon --show
free -h
```

回退时先记录原 `vm.swappiness`，执行 `sudo swapoff /swapfile`，再删除 `/etc/fstab` 中的精确 `/swapfile none swap sw 0 0` 行和 `/etc/sysctl.d/99-museai-swap.conf`，最后执行 `sudo sysctl --system` 并确认已恢复原值；不要直接删除仍处于启用状态的文件。

## 8. 安全提醒

- `.env`、证书私钥、数据库密码永远不进 Git。
- 改完 `.env` 后 `sudo systemctl restart museai-backend` 才生效。
- 曾在聊天、截图或日志中出现过的 AppSecret / LLM key / TTS key，上线前必须轮换。
