# 小程序内容维护指南

本指南面向当前小程序后端。小程序没有普通用户登录；游客使用 session token，管理接口仅接受生产唯一管理员 `test@test.com`。

## 1. 当前内容边界

- `data/museum_template/halls.csv` 中九个展厅的 slug、名称和简介是已确认内容，不应被演示文案或 bootstrap 回退值覆盖。
- `data/museum_test_data/` 的展品是小程序联调数据，不代表馆方真实展品。真实展品快照到位后，沿用稳定来源名 `banpo-museum-data` 做权威导入，即可停用被新快照遗漏的测试记录。
- 地图、展品点位和路线仍待馆方真实数据；CSV 中相关字段留空不代表可用的馆内定位。

## 2. 统一 CSV/XLSX 格式

可以使用同一目录下的 `halls.csv` + `exhibits.csv`，也可以使用只含 `halls` / `exhibits` 两个工作表的 `museum_data.xlsx`。CSV 使用 UTF-8（可带 BOM）。基线表头和详细校验见 [博物馆数据导入规范](./museum-data-import.md)。

`halls` 当前统一表头：

```text
source_record_id,slug,name,description,floor,estimated_duration_minutes,display_order,is_active,suggested_questions,short_description
```

其中 `short_description` 是可选列；它用于小程序展厅卡片的单行短介绍，最多 48 个字符，正式文案建议实际写成 14–18 个字符且不包含换行。更新已有展厅时，省略整列会保留数据库现值；包含该列但单元格留空则会显式清空现值。`description` 仍保存展厅完整简介，不能用短介绍替代。

`exhibits` 当前统一表头：

```text
source_record_id,name,description,hall,floor,category,era,importance,estimated_visit_time,display_order,location_x,location_y,is_active,suggested_questions,image_url
```

### 建议条契约

`suggested_questions` 使用 JSON 字符串数组或 `|` 分隔，最多 6 条。每条问题必须为 8–18 个字符，并以中文问号 `？` 结尾；同时满足：

- 写出展品名称或明确的展签对象；
- 要求观察或核对一项具体信息，如材料、外形、器形、纹饰、位置、制作或使用痕迹；“形制”因过于抽象仍按无效表达拒绝；
- 不讨论“这是不是测试数据”、“真实数据接入后”、“上线后”等维护话题；
- 不使用“眼前这些内容怎样理解”等无对象、无观察目标的模糊表达。

可采用“尖底瓶器形怎么看？”这类日常、可观察的问法；不要改写成“尖底瓶形制怎么看？”。

CSV/XLSX 中只要显式提供的任一建议无效，整个 dry-run/import 批次就会校验失败且不写入；导入器不会静默删除、替换或“修好”无效的 provided suggestion。希望后端自动派生建议时，必须把对应 `suggested_questions` 单元格整体留空。JSON `[]`、`[""]`、混入空字符串的 JSON 列表，以及 `|` / ` || ` 等含空段的分隔文本都属于显式无效值，不等同于留空。

字段留空时，后端才会从可信名称、简介中的具体细节和分类确定性派生建议；即使分类为空且简介没有已知细节锚点，长名称也会先去掉 `【】` 标注和括号副题，再按自然分隔符、可辨编号或对象类型提取主题，并按对象类型生成 1–2 条合格问句。运行时仍执行同一质量规则作为防御性过滤，但不用于挽救导入文件中的无效显式值。只有无法得到可辨可信对象时才返回空列表；不用泛化人格文案填充，也不新增 LLM 调用。

### `image_url` 契约

- 可留空；无图时公开展品 API 返回 `image_url: null`，小程序显示内置默认图。
- 非空值只接受绝对 HTTPS URL，不接受 HTTP、带用户名/密码或 fragment 的 URL。
- CSV 外链适合已有稳定 HTTPS 图片服务的批量数据。如果图片由 MuseAI 服务器管理，先导入展品，再通过管理接口上传。
- 统一模板始终包含 `image_url` 列；重导入时空单元格会清除该展品现有外链。若曾通过管理员 PUT 设置外链，后续快照必须同步保留同一 URL，否则应改用不受该列影响的本地上传图片。

## 3. 数据校验和导入

正式快照必须先 dry-run：

```powershell
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-museum-data --dry-run --authoritative
```

确认九厅、展品数量、停用计划和校验结果后，再执行权威导入：

```powershell
uv run python scripts/import_museum_data.py .\museum_data.xlsx --source-name banpo-museum-data --authoritative
```

仅做日常增量更新时去掉 `--authoritative`。权威模式会停用同来源中本次文件遗漏的记录，不能对不完整增量表误用。正式导入需要 PostgreSQL、Elasticsearch 和 embedding provider；只有 `pending_index=[]` 且命令状态为 0 才算完成。

仓库自带数据可分别验证：

```powershell
uv run python scripts/import_museum_data.py .\data\museum_template --source-name banpo-museum-data --dry-run --authoritative
uv run python scripts/import_museum_data.py .\data\museum_test_data --source-name banpo-museum-data --dry-run --authoritative
```

## 4. 管理员图片维护

上传文件支持单帧 JPEG、PNG 和 WebP，默认最大 5 MiB、最大 4000 万像素。后端会核对文件签名与解码结构，扩展名改伪的非图片会被拒绝。
同一展品的图片替换应串行操作：等待前一次上传返回后再发下一次，避免并发覆盖留下未引用文件；当前只有唯一管理员，也应避免重复点击上传。

在 PowerShell 7 中以交互方式取得 token，不把密码写入文档或命令历史：

```powershell
$securePassword = Read-Host '管理员密码' -AsSecureString
$credential = [pscredential]::new('test@test.com', $securePassword)
$loginBody = @{
  email = $credential.UserName
  password = $credential.GetNetworkCredential().Password
} | ConvertTo-Json
$login = Invoke-RestMethod -Method Post `
  -Uri 'https://api.banpo-museai.xyz/api/v1/auth/login' `
  -ContentType 'application/json' -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }
Remove-Variable loginBody, credential, securePassword
```

上传或替换图片：

```powershell
$exhibitId = '<展品 UUID>'
$image = Get-Item -LiteralPath 'C:\path\to\exhibit.jpg'
Invoke-RestMethod -Method Post `
  -Uri "https://api.banpo-museai.xyz/api/v1/admin/exhibits/$exhibitId/image" `
  -Headers $headers -Form @{ file = $image }
```

成功后返回根相对 API 路径 `/api/v1/exhibits/{id}/image`。通过公开路径验证读取：

```powershell
Invoke-WebRequest -Uri "https://api.banpo-museai.xyz/api/v1/exhibits/$exhibitId/image" -OutFile "$env:TEMP\museai-image-check"
```

删除图片（同时清除本地上传路径和外链）：

```powershell
Invoke-RestMethod -Method Delete `
  -Uri "https://api.banpo-museai.xyz/api/v1/admin/exhibits/$exhibitId/image" `
  -Headers $headers
```

如果需要为单件展品设置 HTTPS 外链，建议先调用上述 DELETE 清除旧上传，再仅更新 `image_url`：

```powershell
$body = @{ image_url = 'https://images.example.org/exhibit.jpg' } | ConvertTo-Json
Invoke-RestMethod -Method Put `
  -Uri "https://api.banpo-museai.xyz/api/v1/admin/exhibits/$exhibitId" `
  -Headers $headers -ContentType 'application/json' -Body $body
```

本地上传优先于外链返回；删除本地上传时当前实现也会清空外链，需要外链时再重新 PUT。
通过 PUT 临时设置的外链仍受下一次 CSV/XLSX 导入约束：统一模板中的空 `image_url` 会将其清空，长期维护应以数据文件为准。

## 5. 生产图片目录

图片必须放在 Git 工作树外的持久目录，避免切换提交或清理工作树时丢失：

```bash
sudo install -d -o ubuntu -g ubuntu -m 0750 /home/ubuntu/museai-data/exhibit-images
```

在 `/home/ubuntu/MuseAI/.env` 中配置：

```dotenv
EXHIBIT_IMAGE_DIR=/home/ubuntu/museai-data/exhibit-images
EXHIBIT_IMAGE_MAX_BYTES=5242880
EXHIBIT_IMAGE_MAX_PIXELS=40000000
```

修改 `.env` 后必须 `sudo systemctl restart museai-backend`。不得把图片根目录配到 `/tmp`、仓库内未跟踪目录或 Nginx 可直接遍历的公开目录。

## 6. 唯一管理员创建和重置

生产只保留 `test@test.com` 的 `admin` 角色。下述命令都在 `/home/ubuntu/MuseAI` 执行，不在脚本、文档、shell history 或 Git 中写入密码。

首次创建（密码由终端隐藏提示读取）：

```bash
DATABASE_URL="$(PYTHONPATH=backend .venv/bin/python -c \
  'from app.config.settings import get_settings; print(get_settings().DATABASE_URL)')" \
  .venv/bin/python scripts/bootstrap_admin.py --email test@test.com
```

该写法由 Pydantic 读取 `.env`，不把 dotenv 当 shell 脚本执行。引导脚本会拒绝第二个管理员。如果 `test@test.com` 已是管理员，重复运行是 no-op，**不会重置密码**。

已有唯一管理员的密码重置使用下列一次性交互命令。命令会先确认当前管理员列表严格等于 `test@test.com`，再写入新哈希：

```bash
PYTHONPATH=backend .venv/bin/python - <<'PY'
import asyncio
import getpass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.infra.postgres.models import User
from app.infra.security.password import hash_password


def validate_password(password: str) -> None:
    checks = (
        len(password) >= 12,
        any(char.isupper() for char in password),
        any(char.islower() for char in password),
        any(char.isdigit() for char in password),
        any(not char.isalnum() and not char.isspace() for char in password),
    )
    if not all(checks):
        raise SystemExit("Password must be 12+ chars with upper/lower/digit/special")


async def main() -> None:
    password = getpass.getpass("New admin password: ")
    validate_password(password)
    engine = create_async_engine(get_settings().DATABASE_URL)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            admins = list((await session.scalars(select(User).where(User.role == "admin"))).all())
            if len(admins) != 1 or admins[0].email != "test@test.com":
                raise SystemExit("Refusing reset: admin set is not exactly test@test.com")
            admins[0].password_hash = hash_password(password)
            await session.commit()
            print("Admin password reset completed for test@test.com")
    finally:
        await engine.dispose()


asyncio.run(main())
PY
```

创建或重置后，使用管理登录 API 实测，并查询数据库确认 `role='admin'` 的记录只有该邮箱。如果存在其他管理员，先停止发布并人工确认降权对象，不要用批量 SQL 猜测处理。

## 7. 生产部署和验收

部署在 2C8G 服务器上串行执行，不同时运行全量测试、依赖同步、迁移和权威导入。以下假设服务器 checkout 为 `/home/ubuntu/MuseAI`，目标代码在 `origin/main`。所有权威命令都必须在 Bash 中执行，并以 `set -euo pipefail` 开始；任一命令失败即停止，不得忽略退出码后继续发布。

1. 初始化本批次回退记录和固定恢复指针：

   ```bash
   set -euo pipefail
   umask 077
   cd /home/ubuntu/MuseAI
   WORKTREE_STATUS="$(git status --porcelain)"
   test -z "$WORKTREE_STATUS"
   test -f .env

   RELEASE_DIR=/home/ubuntu/museai-config-backups
   CURRENT_RELEASE_POINTER="${RELEASE_DIR}/current-release.env"
   sudo install -d -o ubuntu -g ubuntu -m 0700 "$RELEASE_DIR"
   install -d -m 0700 /home/ubuntu/museai-backups

   OLD_SHA="$(git rev-parse HEAD)"
   DEPLOY_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
   ENV_BACKUP="${RELEASE_DIR}/env_${OLD_SHA}_${DEPLOY_STAMP}"
   RELEASE_RECORD="${RELEASE_DIR}/release_${DEPLOY_STAMP}.env"
   cp -p .env "$ENV_BACKUP"
   chmod 600 "$ENV_BACKUP"
   {
       printf 'DEPLOY_STAMP=%q\n' "$DEPLOY_STAMP"
       printf 'RELEASE_RECORD=%q\n' "$RELEASE_RECORD"
       printf 'CURRENT_RELEASE_POINTER=%q\n' "$CURRENT_RELEASE_POINTER"
       printf 'OLD_SHA=%q\n' "$OLD_SHA"
       printf 'ENV_BACKUP=%q\n' "$ENV_BACKUP"
       printf 'DEPLOY_PHASE=%q\n' initialized
   } > "$RELEASE_RECORD"
   chmod 600 "$RELEASE_RECORD"

   POINTER_TMP="$(mktemp "${RELEASE_DIR}/.current-release.XXXXXX")"
   trap 'rm -f -- "${POINTER_TMP:-}"' EXIT
   printf 'RELEASE_RECORD=%q\n' "$RELEASE_RECORD" > "$POINTER_TMP"
   chmod 600 "$POINTER_TMP"
   mv -f -- "$POINTER_TMP" "$CURRENT_RELEASE_POINTER"
   POINTER_TMP=""
   trap - EXIT
   sync "$RELEASE_RECORD" "$CURRENT_RELEASE_POINTER"
   printf 'RELEASE_RECORD=%s\nCURRENT_RELEASE_POINTER=%s\n' "$RELEASE_RECORD" "$CURRENT_RELEASE_POINTER"
   ```

   `current-release.env` 是固定的 `0600` 恢复指针，只保存当前 `RELEASE_RECORD` 路径；真正的 `DEPLOY_STAMP`、回退 SHA、备份路径和阶段都保存在该批次记录中。每完成一步都追加 `DEPLOY_PHASE` 并执行 `sync`，因此 SSH 断线后无需猜测时间戳。

2. SSH 断线、切换 shell 或准备执行后续任一步骤前，用固定指针恢复状态：

   ```bash
   set -euo pipefail
   RELEASE_DIR=/home/ubuntu/museai-config-backups
   CURRENT_RELEASE_POINTER="${RELEASE_DIR}/current-release.env"
   test -f "$CURRENT_RELEASE_POINTER"
   test ! -L "$CURRENT_RELEASE_POINTER"
   test "$(stat -c '%a' "$CURRENT_RELEASE_POINTER")" = 600
   test "$(stat -c '%U' "$CURRENT_RELEASE_POINTER")" = ubuntu
   . "$CURRENT_RELEASE_POINTER"
   : "${RELEASE_RECORD:?current release pointer is incomplete}"
   case "$RELEASE_RECORD" in
       "${RELEASE_DIR}"/release_*.env) ;;
       *) printf 'invalid release record path: %s\n' "$RELEASE_RECORD" >&2; exit 1 ;;
   esac
   test -f "$RELEASE_RECORD"
   test ! -L "$RELEASE_RECORD"
   test "$(stat -c '%a' "$RELEASE_RECORD")" = 600
   test "$(stat -c '%U' "$RELEASE_RECORD")" = ubuntu
   . "$RELEASE_RECORD"
   : "${DEPLOY_STAMP:?missing DEPLOY_STAMP}"
   : "${OLD_SHA:?missing OLD_SHA}"
   : "${ENV_BACKUP:?missing ENV_BACKUP}"
   EFFECTIVE_FINAL_SHA="${FINAL_SHA:-${DOCUMENTATION_SHA:-${TARGET_SHA:-}}}"
   printf 'DEPLOY_STAMP=%s\nDEPLOY_PHASE=%s\nEFFECTIVE_FINAL_SHA=%s\nRELEASE_RECORD=%s\n' \
       "$DEPLOY_STAMP" "$DEPLOY_PHASE" "$EFFECTIVE_FINAL_SHA" "$RELEASE_RECORD"
   ```

3. 备份并校验 PostgreSQL；Compose 的数据库角色显式固定为 `museai`：

   ```bash
   set -euo pipefail
   : "${RELEASE_RECORD:?run the recovery block first}"
   cd /home/ubuntu/MuseAI
   docker ps --format '{{.Names}}' | grep -Fx museai-postgres
   DB_BACKUP="$(PG_CONTAINER=museai-postgres PGUSER=museai DB_NAME=museai BACKUP_DIR=/home/ubuntu/museai-backups bash ./deploy/pg_backup.sh)"
   test -f "$DB_BACKUP"
   gzip -t "$DB_BACKUP"
   DB_BACKUP_SHA256="$(sha256sum "$DB_BACKUP" | awk '{print $1}')"
   {
       printf 'DB_BACKUP=%q\n' "$DB_BACKUP"
       printf 'DB_BACKUP_SHA256=%q\n' "$DB_BACKUP_SHA256"
       printf 'DEPLOY_PHASE=%q\n' db_backup_verified
   } >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD" "$DB_BACKUP"
   printf 'DB_BACKUP=%s\nDB_BACKUP_SHA256=%s\n' "$DB_BACKUP" "$DB_BACKUP_SHA256"
   ```

4. 如果持久图片目录已经存在，对图片文件做同批次备份；PostgreSQL dump 不包含文件本体。目录尚不存在时也要把“不需要图片备份”写入批次记录。

   ```bash
   set -euo pipefail
   : "${RELEASE_RECORD:?run the recovery block first}"
   if [ -d /home/ubuntu/museai-data/exhibit-images ]; then
       IMAGE_BACKUP_REQUIRED=true
       IMAGE_BACKUP="/home/ubuntu/museai-backups/exhibit-images_${OLD_SHA}_${DEPLOY_STAMP}.tar.gz"
       tar -C /home/ubuntu/museai-data -czf "$IMAGE_BACKUP" exhibit-images
       tar -tzf "$IMAGE_BACKUP" >/dev/null
       IMAGE_BACKUP_SHA256="$(sha256sum "$IMAGE_BACKUP" | awk '{print $1}')"
   else
       IMAGE_BACKUP_REQUIRED=false
       IMAGE_BACKUP=""
       IMAGE_BACKUP_SHA256=""
   fi
   {
       printf 'IMAGE_BACKUP_REQUIRED=%q\n' "$IMAGE_BACKUP_REQUIRED"
       printf 'IMAGE_BACKUP=%q\n' "$IMAGE_BACKUP"
       printf 'IMAGE_BACKUP_SHA256=%q\n' "$IMAGE_BACKUP_SHA256"
       printf 'DEPLOY_PHASE=%q\n' image_backup_recorded
   } >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"
   [ -z "$IMAGE_BACKUP" ] || sync "$IMAGE_BACKUP"
   printf 'IMAGE_BACKUP_REQUIRED=%s\nIMAGE_BACKUP=%s\n' "$IMAGE_BACKUP_REQUIRED" "$IMAGE_BACKUP"
   ```

5. 按第 5 节更新 `.env` 后，解析并持久化目标 SHA，再停服、同步依赖、迁移和启动：

   ```bash
   set -euo pipefail
   : "${RELEASE_RECORD:?run the recovery block first}"
   cd /home/ubuntu/MuseAI
   UV=/home/ubuntu/.local/bin/uv
   test -x "$UV"
   sudo install -d -o ubuntu -g ubuntu -m 0750 /home/ubuntu/museai-data/exhibit-images
   git fetch origin main
   TARGET_SHA="$(git rev-parse origin/main)"
   git cat-file -e "${TARGET_SHA}^{commit}"
   while IFS= read -r -d '' tracked_path; do
       case "$tracked_path" in
           .env.example|*/.env.example)
               ;;
           .env|.env.*|*/.env|*/.env.*|\
           .venv|logs|var|uploads|backup|backups|certs|secrets|deploy/ssl|\
           frontend/dist|frontend/node_modules|\
           .venv/*|logs/*|var/*|uploads/*|backup/*|backups/*|\
           certs/*|secrets/*|deploy/ssl/*|frontend/dist/*|frontend/node_modules/*|\
           *.pem|*.key|*.crt|*.cer|*.csr|*.p12|*.pfx|*.jks|*.keystore|\
           *.db|*.sqlite|*.sqlite3|*.log|*.pid|*.sock|\
           museai_*.sql.gz|*/museai_*.sql.gz|\
           exhibit-images_*.tar.gz|*/exhibit-images_*.tar.gz)
               printf 'target commit tracks protected server-local path: %s\n' "$tracked_path" >&2
               exit 1
               ;;
       esac
   done < <(git ls-tree -r --name-only -z "$TARGET_SHA")
   printf 'TARGET_SHA=%q\nDEPLOY_PHASE=%q\n' "$TARGET_SHA" target_resolved >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"

   docker ps --format '{{.Names}}' | grep -Fx museai-postgres
   docker ps --format '{{.Names}}' | grep -Fx museai-redis
   docker ps --format '{{.Names}}' | grep -Fx museai-elasticsearch
   docker update --restart unless-stopped museai-postgres museai-redis museai-elasticsearch >/dev/null
   for container in museai-postgres museai-redis museai-elasticsearch; do
       test "$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$container")" = unless-stopped
   done
   sudo systemctl stop museai-backend
   if sudo systemctl is-active --quiet museai-backend; then
       printf 'museai-backend did not stop\n' >&2
       exit 1
   fi
   printf 'DEPLOY_PHASE=%q\n' service_stopped >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"

   git switch --no-overwrite-ignore --detach "$TARGET_SHA"
   test "$(git rev-parse HEAD)" = "$TARGET_SHA"
   printf 'DEPLOY_PHASE=%q\n' checkout_complete >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"

   "$UV" lock --check
   "$UV" sync --frozen
   "$UV" pip check --python /home/ubuntu/MuseAI/.venv/bin/python
   printf 'DEPLOY_PHASE=%q\n' dependencies_ready >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"

   .venv/bin/alembic upgrade head
   MIGRATION_CURRENT="$(.venv/bin/alembic current)"
   test -n "$MIGRATION_CURRENT"
   printf 'MIGRATION_CURRENT=%q\nDEPLOY_PHASE=%q\n' "$MIGRATION_CURRENT" migration_complete >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"

   sudo systemctl start museai-backend
   printf 'DEPLOY_PHASE=%q\n' service_started >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"
   ```

6. `/api/v1/health` 只证明进程存活；发布门禁必须使用 `/api/v1/ready` 验证 PostgreSQL、Redis 和 Elasticsearch。当前权威链路只有 systemd 的 `127.0.0.1:8000` 与 Nginx HTTPS，不依赖旧 3000 映射。

   ```bash
   set -euo pipefail
   : "${RELEASE_RECORD:?run the recovery block first}"
   sudo systemctl is-active --quiet museai-backend
   sudo systemctl status museai-backend --no-pager -l
   journalctl -u museai-backend -n 100 --no-pager
   curl -fsS http://127.0.0.1:8000/api/v1/health
   curl -fsS http://127.0.0.1:8000/api/v1/ready
   curl -fsS https://api.banpo-museai.xyz/api/v1/health
   curl -fsS https://api.banpo-museai.xyz/api/v1/ready
   systemctl is-enabled --quiet docker
   MAIN_PID="$(systemctl show museai-backend -p MainPID --value)"
   test "$MAIN_PID" -gt 1
   PORT_8000_LISTENERS="$(sudo ss -H -lntp '( sport = :8000 )')"
   PORT_3000_LISTENERS="$(sudo ss -H -lnt '( sport = :3000 )')"
   grep -F '127.0.0.1:8000' <<< "$PORT_8000_LISTENERS"
   grep -F "pid=$MAIN_PID," <<< "$PORT_8000_LISTENERS"
   test -z "$PORT_3000_LISTENERS"
   printf 'DEPLOY_PHASE=%q\n' readiness_verified >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"
   ```

7. 如本批次包含数据快照，先 dry-run，再执行权威导入；完成后抽样验证九厅名称/简介、展品数量、具体建议条、报告统计与 `record_notes` 记录摘要，以及一次“上传→公开读取→删除”图片闭环。当前小程序还应验证“保存本次记录”的复制结果；`exploration_guidance` 只做旧客户端兼容契约检查，不作为当前页面验收重点。全部验收完成后，确认 checkout 仍是运行发布目标，再写入权威 `FINAL_SHA` 和完成状态：

   ```bash
   set -euo pipefail
   : "${RELEASE_RECORD:?run the recovery block first}"
   : "${TARGET_SHA:?release record has no TARGET_SHA}"
   cd /home/ubuntu/MuseAI
   test -z "$(git status --porcelain)"
   FINAL_SHA="$(git rev-parse HEAD)"
   test "$FINAL_SHA" = "$TARGET_SHA"
   {
       printf 'FINAL_SHA=%q\n' "$FINAL_SHA"
       printf 'DEPLOY_PHASE=%q\n' final_sha_recorded
       printf 'DEPLOY_PHASE=%q\n' completed
   } >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"
   ```

   `TARGET_SHA` 表示实际执行依赖同步、迁移、启动和 readiness 验证的运行发布提交；`FINAL_SHA` 表示关闭记录时服务器最终 checkout。旧记录读取时使用 `FINAL_SHA > DOCUMENTATION_SHA > TARGET_SHA` 的兼容优先级。三者都不存在时必须停止，不能猜测。

8. 发布证据通常应在运行发布前写完。确需在验收后补充本批次 README、部署说明、维护指南、`STATE.md` 或 changelog 时，只允许同步下列纯 Markdown 文档后代，并同时更新 `DOCUMENTATION_SHA` 与 `FINAL_SHA`；出现任何其他文件差异都必须作为新发布重新执行本节：

   ```bash
   set -euo pipefail
   : "${RELEASE_RECORD:?run the recovery block first}"
   : "${TARGET_SHA:?release record has no TARGET_SHA}"
   cd /home/ubuntu/MuseAI
   test -z "$(git status --porcelain)"
   git fetch origin main
   DOCUMENTATION_SHA="$(git rev-parse origin/main)"
   git cat-file -e "${DOCUMENTATION_SHA}^{commit}"
   git merge-base --is-ancestor "$TARGET_SHA" "$DOCUMENTATION_SHA"
   while IFS= read -r -d '' changed_path; do
       case "$changed_path" in
          README.md|README_EN.md|deploy/DEPLOYMENT_NOTES.md|docs/miniapp-content-maintenance.md|docs/server-storage-layout.md|docs/logs/CHANGELOG.md) ;;
           *) printf 'post-deploy commit changes runtime path: %s\n' "$changed_path" >&2; exit 1 ;;
       esac
   done < <(git diff --name-only -z "$TARGET_SHA" "$DOCUMENTATION_SHA")
   git switch --no-overwrite-ignore --detach "$DOCUMENTATION_SHA"
   FINAL_SHA="$(git rev-parse HEAD)"
   test "$FINAL_SHA" = "$DOCUMENTATION_SHA"
   {
       printf 'DOCUMENTATION_SHA=%q\n' "$DOCUMENTATION_SHA"
       printf 'FINAL_SHA=%q\n' "$FINAL_SHA"
       printf 'DEPLOY_PHASE=%q\n' documentation_synced
       printf 'DEPLOY_PHASE=%q\n' completed
   } >> "$RELEASE_RECORD"
   sync "$RELEASE_RECORD"
   ```

## 8. 正式上线前、上线当天和上线后

本节定义发布节奏和验收责任。代码切换仍完整执行第 7 节，数据库/图片/代码回退仍完整执行第 9 节；不要从本节摘取部分命令替代它们。

### 8.1 先判断变更类型

| 变更 | 发布要求 |
| --- | --- |
| 仅小程序前端，后端契约不变 | 不部署、不重启后端；只验证公网 readiness 和旧接口可用 |
| 后端代码或依赖 | 完整执行第 7 节精确 SHA 发布；前端仍在审核时必须保持向后兼容 |
| Alembic 迁移 | 与代码作为同一批次备份和发布；迁移失败立即停止，不启动错误 schema |
| 真实展厅/展品 CSV/XLSX | 先 dry-run，再以稳定 `source-name` 导入；完整快照才允许 `--authoritative` |
| 管理员上传图片 | 数据库记录和持久图片目录作为同一回退批次维护 |
| 仅 `.env` 中受控配置 | 先备份配置，重启 systemd，并重新验证 health、readiness 和对应业务探针 |

破坏性接口、真实数据全量替换、模型切换和微信正式审核不要挤在同一窗口。优先拆成“后端兼容发布 → 数据发布 → 小程序发布”三个可单独回退的阶段。

### 8.2 正式上线前门禁

以下检查必须有可保存的结果；任何关键项不明确时停止上线，而不是在生产服务器临时试错：

1. **版本和验证**
   - 本地/CI 已验证目标 `origin/main` 的精确 SHA、锁文件、迁移单 head、相关 pytest 和数据 dry-run。
   - 前端候选版本已记录精确 SHA，并通过关闭合法域名豁免后的真机闭环；若涉及布局、媒体或权限，完成 iOS/Android 抽样。
   - 生产服务器不运行全量测试；2C8G 上依赖同步、迁移、导入和重启必须串行。
2. **内容和平台**
   - 九厅名称、简介和开放状态经过确认；真实展品、来源、所属展厅、图片授权和建议条完成抽样。
   - `【测试】` 或其他联调标记不会作为馆方真实内容发布；地图/点位/路线未接入时不伪造定位能力。
   - OCR 已明确为“购买配置并验收”或“隐藏入口、保留文字搜索”之一。
   - 微信隐私政策、用户协议、相机/语音权限和 AI 内容说明与实际功能一致。
3. **生产服务和安全**
   - `test@test.com` 是唯一管理员；不创建小程序普通用户账号。
   - 第三方模型和语音服务的负责人、额度、付费、限流、告警和轮换只记录在私有运维资料中；曾暴露的凭据已轮换。
   - `.env`、证书、数据库、上传图片、日志和备份均留在 Git 工作树外或受保护的服务器本地路径。
   - `sudo nginx -t`、证书引用/到期时间、systemd、Docker 依赖、端口和公网 `/api/v1/ready` 均正常；旧 3000 端口保持关闭。
4. **备份和回退**
   - 每日备份 timer 为 enabled/active，最近备份通过 `gzip -t` 和校验和检查。
   - 正式上线前至少完成一次 `deploy/DEPLOYMENT_NOTES.md` 第 4 节的临时库恢复演练。
   - 本批次已明确代码回退 SHA、数据库备份、图片备份、配置备份和负责人。

### 8.3 上线当天顺序

1. 冻结后端 SHA、前端 SHA、数据来源版本和图片批次，建立发布记录。
2. 如需后端变更，先完整执行第 7 节并让旧小程序完成 session、展厅目录、SSE、TTS 和报告探针。
3. 如需真实数据更新，在后端稳定后单独执行 dry-run 和导入；抽查九厅、展品数量、停用计划、图片和 Elasticsearch 索引状态。
4. 如需图片更新，串行上传并抽查公开 URL；不要同时并发替换同一展品图片。
5. 后端、数据和图片稳定后，才提交或发布小程序候选版本。
6. 记录实际完成时间、最终 SHA、迁移 head、数据来源、备份路径/校验和、前端版本和验证结果。

如果某阶段失败，停止后续阶段并保留现场。不要为了赶窗口跳过第 7 节的备份、精确 checkout、迁移或 readiness 门禁。

### 8.4 发布后 30 分钟和首个 24 小时

发布后立即从正式入口完成一次冷启动闭环，并在服务器检查：

```bash
set -euo pipefail
sudo systemctl is-active --quiet museai-backend
sudo systemctl show museai-backend -p MainPID -p NRestarts --no-pager
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ready
curl -fsS https://api.banpo-museai.xyz/api/v1/ready
sudo journalctl -u museai-backend --since '30 minutes ago' --no-pager
df -h /
free -h
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

验收内容：

- 创建游客 session、加载九厅和展品目录、完成一次 SSE 回答、TTS 和报告。
- 抽查真实展品名称/简介/所属展厅、建议条和图片；确认没有测试标记或跨厅内容。
- 检查 5xx、报告失败、SSE 中断、TTS 认证/限流、数据库/Redis/Elasticsearch readiness 和 systemd 重启。
- 不在共享记录中粘贴 token、游客原始对话、密码或第三方凭据；只记录聚合计数和脱敏错误。
- 首个 24 小时确认每日数据库备份成功；有真实上传图片时确认图片也有同批次可恢复资产。

### 8.5 稳定运行后的维护节奏

- 每日：公网 readiness、关键错误、systemd 重启次数、磁盘/内存、第三方服务额度和最近数据库备份。
- 每周：抽样完整导览和真实数据；校验一份备份并定期执行临时库恢复演练；检查图片备份、磁盘增长和证书到期时间。
- 每次数据更新：保留 dry-run、来源名、权威/增量模式、数量变化、停用计划和抽样结果。
- 每次配置更新：备份 `.env`，记录变更目的但不记录取值，重启并验证对应业务能力。
- 每次代码发布：重新执行第 7 节，不因“仅文档之外的一点小改动”跳过精确 SHA 和回退记录。

### 8.6 停止发布或回退的触发条件

出现下列任一情况，应停止继续发布、保存日志与批次记录，并评估第 9 节回退：

- 内网或公网 `/api/v1/ready` 非 healthy，依赖持续失败或 systemd 反复重启。
- session、SSE、TTS、展厅目录或报告主链路持续 5xx/超时，且无法通过受控配置立即恢复。
- 导入数量、停用计划、展厅归属或图片批次与审批结果不一致。
- 测试数据冒充馆方内容、跨厅回答、管理员数量异常、鉴权绕过或敏感信息暴露。
- 数据库迁移失败、schema 与代码不匹配，或备份/恢复证据缺失。

内容错误但服务健康时，优先停止错误来源的后续导入并按同一数据批次恢复；代码/迁移错误使用第 9 节的精确回退。不得通过清空游客本地缓存、放宽 schema 或临时打开旧 3000 端口掩盖生产故障。

## 9. 回退

回退前先保存当前失败现场、日志、数据库和图片目录。因为 systemd 启动前会执行当前 checkout 的 `alembic upgrade head`，旧 checkout 不认识新 revision；因此不得只切代码而保留数据库 head `20260809_trusted_hall_chat_history`。

如果本批次没有需要保留的新图片引用或新数据，可在新迁移文件仍在 checkout 时先降级一级，再恢复部署前 `.env` 和代码：

```bash
set -euo pipefail
: "${RELEASE_RECORD:?run section 7 recovery block first}"
cd /home/ubuntu/MuseAI
UV=/home/ubuntu/.local/bin/uv
test -x "$UV"
FAILED_STATE_DB_BACKUP="$(PG_CONTAINER=museai-postgres PGUSER=museai DB_NAME=museai BACKUP_DIR=/home/ubuntu/museai-backups bash ./deploy/pg_backup.sh)"
gzip -t "$FAILED_STATE_DB_BACKUP"
FAILED_STATE_DB_BACKUP_SHA256="$(sha256sum "$FAILED_STATE_DB_BACKUP" | awk '{print $1}')"
printf 'FAILED_STATE_DB_BACKUP=%q\nFAILED_STATE_DB_BACKUP_SHA256=%q\nDEPLOY_PHASE=%q\n' \
    "$FAILED_STATE_DB_BACKUP" "$FAILED_STATE_DB_BACKUP_SHA256" rollback_snapshot_verified >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD" "$FAILED_STATE_DB_BACKUP"
sudo systemctl stop museai-backend
if sudo systemctl is-active --quiet museai-backend; then
    printf 'museai-backend did not stop\n' >&2
    exit 1
fi
.venv/bin/alembic downgrade 20260809_exhibit_images
cp -p "$ENV_BACKUP" .env
chmod 600 .env
git switch --no-overwrite-ignore --detach "$OLD_SHA"
test "$(git rev-parse HEAD)" = "$OLD_SHA"
"$UV" lock --check
"$UV" sync --frozen
"$UV" pip check --python /home/ubuntu/MuseAI/.venv/bin/python
sudo systemctl start museai-backend
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ready
curl -fsS https://api.banpo-museai.xyz/api/v1/ready
printf 'DEPLOY_PHASE=%q\n' rollback_complete >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD"
```

如果必须连数据一起回退，必须先完成 [`deploy/DEPLOYMENT_NOTES.md` 的临时数据库恢复演练](../deploy/DEPLOYMENT_NOTES.md#4-配置每日数据库备份)，再执行下列生产恢复。流程先把目标备份恢复到候选库并验证，再停服切换；旧生产库会保留为 `museai_before_restore_*`，验收前不得删除。

```bash
set -euo pipefail
: "${RELEASE_RECORD:?run section 7 recovery block first}"
: "${DB_BACKUP:?release record has no DB_BACKUP}"
: "${DB_BACKUP_SHA256:?release record has no DB_BACKUP_SHA256}"
cd /home/ubuntu/MuseAI
PG_CONTAINER=museai-postgres
PGUSER=museai
DB_NAME=museai
test -f "$DB_BACKUP"
gzip -t "$DB_BACKUP"
test "$(sha256sum "$DB_BACKUP" | awk '{print $1}')" = "$DB_BACKUP_SHA256"

PRE_RESTORE_DB_BACKUP="$(PG_CONTAINER="$PG_CONTAINER" PGUSER="$PGUSER" DB_NAME="$DB_NAME" BACKUP_DIR=/home/ubuntu/museai-backups bash ./deploy/pg_backup.sh)"
gzip -t "$PRE_RESTORE_DB_BACKUP"
PRE_RESTORE_DB_BACKUP_SHA256="$(sha256sum "$PRE_RESTORE_DB_BACKUP" | awk '{print $1}')"

RESTORE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CANDIDATE_DB="museai_restore_candidate_${RESTORE_STAMP//[^A-Za-z0-9_]/_}_$$"
FAILED_DB="museai_before_restore_${RESTORE_STAMP//[^A-Za-z0-9_]/_}_$$"
case "$CANDIDATE_DB:$FAILED_DB" in
    museai_restore_candidate_*:museai_before_restore_*) ;;
    *) printf 'unsafe generated database names\n' >&2; exit 1 ;;
esac
{
    printf 'PRE_RESTORE_DB_BACKUP=%q\n' "$PRE_RESTORE_DB_BACKUP"
    printf 'PRE_RESTORE_DB_BACKUP_SHA256=%q\n' "$PRE_RESTORE_DB_BACKUP_SHA256"
    printf 'RESTORE_STAMP=%q\n' "$RESTORE_STAMP"
    printf 'CANDIDATE_DB=%q\n' "$CANDIDATE_DB"
    printf 'FAILED_DB=%q\n' "$FAILED_DB"
    printf 'DEPLOY_PHASE=%q\n' restore_candidate_planned
} >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD" "$PRE_RESTORE_DB_BACKUP"
EXISTING_RESTORE_DBS="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname IN ('$CANDIDATE_DB', '$FAILED_DB') LIMIT 1")"
test -z "$EXISTING_RESTORE_DBS"
docker exec "$PG_CONTAINER" createdb -U "$PGUSER" "$CANDIDATE_DB"
gzip -dc "$DB_BACKUP" | docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$CANDIDATE_DB"
CANDIDATE_SCHEMA_OK="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$CANDIDATE_DB" -Atqc "SELECT (to_regclass('public.alembic_version') IS NOT NULL AND to_regclass('public.halls') IS NOT NULL)::text")"
test "$CANDIDATE_SCHEMA_OK" = true
CANDIDATE_REVISION="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$CANDIDATE_DB" -Atqc 'SELECT version_num FROM alembic_version LIMIT 1')"
test -n "$CANDIDATE_REVISION"
printf 'DEPLOY_PHASE=%q\n' restore_candidate_verified >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD"

sudo systemctl stop museai-backend
if sudo systemctl is-active --quiet museai-backend; then
    printf 'museai-backend did not stop\n' >&2
    exit 1
fi
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$DB_NAME', '$CANDIDATE_DB') AND pid <> pg_backend_pid();"
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d postgres -c \
    "ALTER DATABASE \"$DB_NAME\" RENAME TO \"$FAILED_DB\";"
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d postgres -c \
    "ALTER DATABASE \"$CANDIDATE_DB\" RENAME TO \"$DB_NAME\";"
PRODUCTION_SCHEMA_OK="$(docker exec "$PG_CONTAINER" psql -U "$PGUSER" -d "$DB_NAME" -Atqc "SELECT (to_regclass('public.alembic_version') IS NOT NULL AND to_regclass('public.halls') IS NOT NULL)::text")"
test "$PRODUCTION_SCHEMA_OK" = true
{
    printf 'RESTORED_DB_BACKUP=%q\n' "$DB_BACKUP"
    printf 'DEPLOY_PHASE=%q\n' database_restored
} >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD" "$PRE_RESTORE_DB_BACKUP"
printf 'old production database retained as %s\n' "$FAILED_DB"
```

如果第二次重命名失败，`set -e` 会立即停止且服务保持关闭；原库仍以输出的 `FAILED_DB` 名称存在。先检查 `docker exec museai-postgres psql -U museai -d postgres -lqt`，确认没有名为 `museai` 的库后，才可把 `FAILED_DB` 显式重命名回 `museai`。不得在错误状态下继续启动服务。

恢复图片前先校验 SHA-256，再用 Python 拒绝绝对路径、`..`、链接和设备条目；只允许 `exhibit-images/` 子树进入同文件系统暂存目录。旧图片目录同样保留到验收完成：

```bash
set -euo pipefail
: "${RELEASE_RECORD:?run section 7 recovery block first}"
: "${IMAGE_BACKUP:?release record has no IMAGE_BACKUP}"
: "${IMAGE_BACKUP_SHA256:?release record has no IMAGE_BACKUP_SHA256}"
cd /home/ubuntu/MuseAI
test -f "$IMAGE_BACKUP"
test ! -L "$IMAGE_BACKUP"
tar -tzf "$IMAGE_BACKUP" >/dev/null
test "$(sha256sum "$IMAGE_BACKUP" | awk '{print $1}')" = "$IMAGE_BACKUP_SHA256"
.venv/bin/python - "$IMAGE_BACKUP" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

archive = sys.argv[1]
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    if not members:
        raise SystemExit("image archive is empty")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe image archive path: {member.name}")
        if not path.parts or path.parts[0] != "exhibit-images":
            raise SystemExit(f"unexpected image archive root: {member.name}")
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise SystemExit(f"unsupported image archive entry: {member.name}")
PY

IMAGE_STAGE="$(mktemp -d /home/ubuntu/museai-data/.exhibit-images-restore.XXXXXX)"
trap 'rm -rf -- "${IMAGE_STAGE:-}"' EXIT
tar -xzf "$IMAGE_BACKUP" -C "$IMAGE_STAGE" --no-same-owner --no-same-permissions
test -d "$IMAGE_STAGE/exhibit-images"
test "$(sha256sum "$IMAGE_BACKUP" | awk '{print $1}')" = "$IMAGE_BACKUP_SHA256"
sudo systemctl stop museai-backend
if sudo systemctl is-active --quiet museai-backend; then
    printf 'museai-backend did not stop\n' >&2
    exit 1
fi
IMAGE_DIR=/home/ubuntu/museai-data/exhibit-images
FAILED_IMAGE_DIR="/home/ubuntu/museai-data/exhibit-images.before_restore_${DEPLOY_STAMP}"
test ! -e "$FAILED_IMAGE_DIR"
if [ -e "$IMAGE_DIR" ]; then
    test ! -L "$IMAGE_DIR"
    printf 'FAILED_IMAGE_DIR=%q\nDEPLOY_PHASE=%q\n' "$FAILED_IMAGE_DIR" image_swap_planned >> "$RELEASE_RECORD"
    sync "$RELEASE_RECORD"
    mv -- "$IMAGE_DIR" "$FAILED_IMAGE_DIR"
else
    FAILED_IMAGE_DIR=""
    printf 'FAILED_IMAGE_DIR=%q\nDEPLOY_PHASE=%q\n' "$FAILED_IMAGE_DIR" image_swap_planned >> "$RELEASE_RECORD"
    sync "$RELEASE_RECORD"
fi
mv -- "$IMAGE_STAGE/exhibit-images" "$IMAGE_DIR"
chown -R ubuntu:ubuntu "$IMAGE_DIR"
IMAGE_STAGE=""
trap - EXIT
printf 'FAILED_IMAGE_DIR=%q\nRESTORED_IMAGE_BACKUP=%q\nDEPLOY_PHASE=%q\n' \
    "$FAILED_IMAGE_DIR" "$IMAGE_BACKUP" images_restored >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD"
```

数据库和必要图片恢复成功后，再恢复同批次配置与代码并验证 readiness：

```bash
set -euo pipefail
: "${RELEASE_RECORD:?run section 7 recovery block first}"
cd /home/ubuntu/MuseAI
UV=/home/ubuntu/.local/bin/uv
test -x "$UV"
cp -p "$ENV_BACKUP" .env
chmod 600 .env
git switch --no-overwrite-ignore --detach "$OLD_SHA"
test "$(git rev-parse HEAD)" = "$OLD_SHA"
"$UV" lock --check
"$UV" sync --frozen
"$UV" pip check --python /home/ubuntu/MuseAI/.venv/bin/python
sudo systemctl start museai-backend
sudo systemctl is-active --quiet museai-backend
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ready
curl -fsS https://api.banpo-museai.xyz/api/v1/ready
printf 'DEPLOY_PHASE=%q\n' data_rollback_verified >> "$RELEASE_RECORD"
sync "$RELEASE_RECORD"
```

只有在回退验收、管理员核对、九厅内容和图片读取都通过后，才可人工删除记录中的 `FAILED_DB`、`FAILED_IMAGE_DIR` 和候选失败库；删除前再次核对名称前缀，绝不能对当前 `museai` 库或当前 `exhibit-images` 目录执行删除。

回退后重复健康检查、唯一管理员核对、九厅名称/简介抽样和公开展品 API 验证，不要只以 systemd `active` 作为回退成功标准。
