# 小程序内容维护指南

本指南面向当前小程序后端。小程序没有普通用户登录；游客使用 session token，管理接口仅接受生产唯一管理员 `test@test.com`。

## 1. 当前内容边界

- `data/museum_template/halls.csv` 中九个展厅的 slug、名称和简介是已确认内容，不应被演示文案或 bootstrap 回退值覆盖。
- `data/museum_test_data/` 的展品是小程序联调数据，不代表馆方真实展品。真实展品快照到位后，沿用稳定来源名 `banpo-museum-data` 做权威导入，即可停用被新快照遗漏的测试记录。
- 地图、展品点位和路线仍待馆方真实数据；CSV 中相关字段留空不代表可用的馆内定位。

## 2. 统一 CSV/XLSX 格式

可以使用同一目录下的 `halls.csv` + `exhibits.csv`，也可以使用只含 `halls` / `exhibits` 两个工作表的 `museum_data.xlsx`。CSV 使用 UTF-8（可带 BOM）。基线表头和详细校验见 [博物馆数据导入规范](./museum-data-import.md)。

`exhibits` 当前统一表头：

```text
source_record_id,name,description,hall,floor,category,era,importance,estimated_visit_time,display_order,location_x,location_y,is_active,suggested_questions,image_url
```

### 建议条契约

`suggested_questions` 使用 JSON 字符串数组或 `|` 分隔，最多 6 条、每条最多 120 字。每条问题应同时满足：

- 写出展品名称或明确的展签对象；
- 要求观察或核对一项具体信息，如材料、形制、纹饰、位置、制作或使用痕迹；
- 不讨论“这是不是测试数据”、“真实数据接入后”、“上线后”等维护话题；
- 不使用“眼前这些内容怎样理解”等无对象、无观察目标的模糊表达。

后端运行时会再做质量过滤。展品已有可信名称时，不合格建议可由名称、简介中的具体细节和分类确定性替换；无可信上下文时返回空列表，不用泛化人格文案填充，也不新增 LLM 调用。

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

部署在 2C8G 服务器上串行执行，不同时运行全量测试、依赖同步、迁移和权威导入。以下假设服务器 checkout 为 `/home/ubuntu/MuseAI`，目标代码在 `origin/codex/data-driven-miniapp-framework`。

1. 记录回退点并备份 PostgreSQL：

   ```bash
   cd /home/ubuntu/MuseAI
   test -z "$(git status --porcelain)"
   OLD_SHA="$(git rev-parse HEAD)"
   DEPLOY_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
   sudo install -d -o ubuntu -g ubuntu -m 0700 /home/ubuntu/museai-config-backups
   ENV_BACKUP="/home/ubuntu/museai-config-backups/env_${OLD_SHA}_${DEPLOY_STAMP}"
   RELEASE_RECORD="/home/ubuntu/museai-config-backups/release_${DEPLOY_STAMP}.env"
   cp -p .env "$ENV_BACKUP"
   chmod 600 "$ENV_BACKUP"
   printf 'OLD_SHA=%q\nENV_BACKUP=%q\n' "$OLD_SHA" "$ENV_BACKUP" > "$RELEASE_RECORD"
   chmod 600 "$RELEASE_RECORD"
   printf 'RELEASE_RECORD=%s\n' "$RELEASE_RECORD"
   docker ps --format '{{.Names}}'
   PG_CONTAINER=<postgres容器名> DB_NAME=museai BACKUP_DIR=/home/ubuntu/museai-backups ./deploy/pg_backup.sh
   ```

   将输出的 `RELEASE_RECORD` 绝对路径记入发布记录。SSH 断线或更换 shell 后，先执行 `set -a; . '<该路径>'; set +a` 恢复由本流程生成的 `OLD_SHA` / `ENV_BACKUP`，不要依赖旧 shell 内存。

2. 如果已有上传图片，对图片目录做同批次备份；PostgreSQL dump 不包含文件本体。

   ```bash
   tar -C /home/ubuntu/museai-data -czf "/home/ubuntu/museai-backups/exhibit-images_${OLD_SHA}.tar.gz" exhibit-images
   ```

3. 创建持久图片目录，按第 5 节更新 `.env`，再切换到已推送且已核对的目标 SHA：

   ```bash
   sudo install -d -o ubuntu -g ubuntu -m 0750 /home/ubuntu/museai-data/exhibit-images
   git fetch origin codex/data-driven-miniapp-framework
   TARGET_SHA="$(git rev-parse origin/codex/data-driven-miniapp-framework)"
   printf 'TARGET_SHA=%q\n' "$TARGET_SHA" >> "$RELEASE_RECORD"
   git switch --detach "$TARGET_SHA"
   uv lock --check
   sudo systemctl stop museai-backend
   uv sync --frozen
   uv pip check --python /home/ubuntu/MuseAI/.venv/bin/python
   .venv/bin/alembic upgrade head
   .venv/bin/alembic current
   sudo systemctl start museai-backend
   ```

4. 验证内外健康检查和迁移 head：

   ```bash
   sudo systemctl status museai-backend --no-pager -l
   journalctl -u museai-backend -n 100 --no-pager
   curl -fsS http://127.0.0.1:8000/api/v1/health
   curl -fsS http://127.0.0.1:3000/api/v1/health
   curl -fsS https://api.banpo-museai.xyz/api/v1/health
   ```

5. 如本批次包含数据快照，先 dry-run，再执行权威导入；完成后抽样验证九厅名称/简介、展品数量、具体建议条、报告 `exploration_guidance` 和一次“上传→公开读取→删除”图片闭环。

## 8. 回退

回退前先保存当前失败现场、日志、数据库和图片目录。因为 systemd 启动前会执行当前 checkout 的 `alembic upgrade head`，旧 checkout 不认识新 revision；因此不得只切代码而保留数据库的 `20260809_exhibit_images` revision。

如果本批次没有需要保留的新图片引用或新数据，可在新迁移文件仍在 checkout 时先降级一级，再恢复部署前 `.env` 和代码：

```bash
cd /home/ubuntu/MuseAI
sudo systemctl stop museai-backend
.venv/bin/alembic downgrade 20260808_remove_legacy_halls
cp -p "$ENV_BACKUP" .env
chmod 600 .env
git switch --detach "$OLD_SHA"
uv lock --check
uv sync --frozen
uv pip check --python /home/ubuntu/MuseAI/.venv/bin/python
sudo systemctl start museai-backend
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:3000/api/v1/health
```

如果必须连数据一起回退，优先在停服状态将部署前 PostgreSQL dump 恢复到经验证的库，同时恢复同批次图片压缩包和 `.env` 备份，然后切回 `OLD_SHA` 再启动服务。如果图片记录已由用户维护，不要直接执行上述 downgrade 丢弃其数据，应先从备份确认恢复点。数据库恢复的详命令和演练要求见 [`deploy/DEPLOYMENT_NOTES.md`](../deploy/DEPLOYMENT_NOTES.md)。

回退后重复健康检查、唯一管理员核对、九厅名称/简介抽样和公开展品 API 验证，不要只以 systemd `active` 作为回退成功标准。
