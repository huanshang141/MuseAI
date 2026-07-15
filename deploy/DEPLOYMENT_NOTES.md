# MuseAI 后端生产部署说明

本目录提供生产运维所需的部署资产。**所有命令都在服务器上手工执行，本仓库不会自动部署。**

资产清单：

| 文件 | 用途 |
| --- | --- |
| `museai-backend.service` | systemd unit，托管 uvicorn 后端进程 |
| `logrotate-museai` | 后端 `logs/*.log` 日志轮转规则 |
| `pg_backup.sh` | PostgreSQL 每日备份脚本 |
| `nginx.conf` | HTTPS 反代参考配置（已在线上使用，以线上实际为准） |

以下命令均假设代码位于 `/home/ubuntu/MuseAI`，路径不同请先全局替换。

HTTPS 证书约定放在 `/etc/nginx/ssl/museai/`：

- `/etc/nginx/ssl/museai/fullchain.pem`
- `/etc/nginx/ssl/museai/privkey.pem`

上传到 `/tmp` 的证书文件不会自动生效；必须复制到 Nginx 配置读取的路径，并执行 `sudo nginx -t && sudo systemctl reload nginx`。

---

## 0. 每次拉取代码后的必做步骤

后端模型和数据库 schema 必须一起更新。拉取代码后，先执行 Alembic 迁移，再重启后端：

```bash
cd /home/ubuntu/MuseAI
git pull origin main
uv run alembic upgrade head
uv run alembic current
pkill -f "uv run uvicorn backend.app.main:app" || true
nohup uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > backend_uvicorn.log 2>&1 &
```

如果已切换到 systemd，则用：

```bash
sudo systemctl restart museai-backend
journalctl -u museai-backend -n 100 --no-pager
```

报告接口 `POST /api/v1/tour/sessions/:id/report` 和 `GET /api/v1/tour/sessions/:id/report` 同时返回 500，且其他 tour/chat/exhibits 接口正常时，优先检查是否漏跑了迁移。当前报告摘要功能需要 `tour_reports.record_summary` 字段；如果数据库仍是旧 schema，ORM 读写报告表会直接触发 500。

## 1. 安装 systemd service

```bash
# 1) 按锁文件同步依赖并确认虚拟环境命令存在
uv lock --check
uv sync --frozen
uv pip check --python /home/ubuntu/MuseAI/.venv/bin/python
test -x /home/ubuntu/MuseAI/.venv/bin/alembic
test -x /home/ubuntu/MuseAI/.venv/bin/uvicorn

# 2) 如代码路径不同，编辑 unit 中的 ExecStart / WorkingDirectory / EnvironmentFile
sudo cp /home/ubuntu/MuseAI/deploy/museai-backend.service /etc/systemd/system/

# 3) 先手工确认迁移可执行
cd /home/ubuntu/MuseAI
uv run alembic upgrade head
uv run alembic current

# 4) 注册并启动
sudo systemctl daemon-reload
sudo systemctl enable --now museai-backend
```

注意：

- 切换到 systemd 前，先停掉手动 nohup 进程：
  `pkill -f "uv run uvicorn backend.app.main:app" || true`
- `EnvironmentFile` 指向 `/home/ubuntu/MuseAI/.env`。systemd 对该文件解析较严格：值含空格必须加引号、不能有 `export`。应用本身也会通过 pydantic-settings 读取同一份 `.env`，两者保持一致即可。
- `uv.lock` 必须由 Git 跟踪。`uv lock --check` 失败或 `uv pip check` 报缺包时禁止重启服务；不要让服务器保留一个覆盖仓库状态的未跟踪旧锁文件。
- unit 直接调用当前 checkout 的 `.venv/bin/alembic` 与 `.venv/bin/uvicorn`，避免长期运行的 `uv run` 父进程与后续 `uv run` 运维命令发生环境锁等待；因此每次切换提交后必须先执行 `uv sync --frozen`。
- unit 会在启动前执行 `.venv/bin/alembic upgrade head`。没有待执行 revision 时该命令是幂等的；如果迁移失败，服务不会在错误 schema 上启动。
- 不要给生产 unit 加 `--reload`。

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
sudo mkdir -p /var/backups/museai
sudo chown ubuntu:ubuntu /var/backups/museai
chmod +x /home/ubuntu/MuseAI/deploy/pg_backup.sh

# 先手工跑一次确认可用（PostgreSQL 跑在 docker compose 里时用 PG_CONTAINER）：
docker ps --format '{{.Names}}'    # 找到 postgres 容器名
PG_CONTAINER=<postgres容器名> DB_NAME=museai /home/ubuntu/MuseAI/deploy/pg_backup.sh
```

成功后添加 cron（每日 03:30）：

```bash
crontab -e
# 添加一行（容器名按实际替换）：
30 3 * * * PG_CONTAINER=<postgres容器名> DB_NAME=museai BACKUP_DIR=/var/backups/museai /home/ubuntu/MuseAI/deploy/pg_backup.sh >> /var/backups/museai/backup.log 2>&1
```

脚本默认保留 7 天（`RETENTION_DAYS` 可调），不在任何位置硬编码密码。

**上线前必须做一次恢复演练**：

```bash
gunzip -c /var/backups/museai/museai_<时间戳>.sql.gz | docker exec -i <postgres容器名> psql -U postgres -d museai_restore_test
```

确认能建出完整表结构和数据后再视备份为有效。

## 5. 验证 health

```bash
curl -i http://127.0.0.1:8000/api/v1/health          # 后端直连
curl -i https://api.banpo-museai.xyz/api/v1/health   # 经 Nginx HTTPS
sudo ss -lntp | grep -E ':80|:443|:8000|:3000'       # 端口监听检查
```

重启服务器后再验证一轮，确认 `enable` 生效（开机自启）。

## 6. 关闭公网 3000 端口（时机很重要）

**前提：小程序已切换 HTTPS 域名，且关闭开发者工具"不校验合法域名"豁免后真机全链路（REST + SSE + TTS）验证通过。在此之前保留 3000，它是当前唯一的调试回退入口。**

满足前提后：

1. 腾讯云控制台 → 轻量应用服务器 → 防火墙：删除 3000 端口入站规则。
2. 如果 3000 是 docker 端口映射（`0.0.0.0:3000->8000`），把 compose/启动参数改为只绑定本机：`127.0.0.1:3000:8000`，或直接去掉该映射。
3. 验证：
   ```bash
   curl -m 5 -i http://122.152.232.190:3000/api/v1/health   # 应超时或拒绝
   curl -i https://api.banpo-museai.xyz/api/v1/health        # 应正常
   ```
4. 同时确认 5432/6379/9200（PostgreSQL/Redis/Elasticsearch）均未对公网开放。

## 7. 安全提醒

- `.env`、证书私钥、数据库密码永远不进 Git。
- 改完 `.env` 后 `sudo systemctl restart museai-backend` 才生效。
- 曾在聊天、截图或日志中出现过的 AppSecret / LLM key / TTS key，上线前必须轮换。
