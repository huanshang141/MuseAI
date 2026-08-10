# MuseAI 服务器直拉部署与存储边界

## 已确认的最小方案

服务器继续使用 `/home/ubuntu/MuseAI` 作为后端仓库和运行目录，直接从
`origin/codex/data-driven-miniapp-framework` 获取精确提交后部署。本方案不迁移到
`/srv/museai`，不移动 Docker 根目录或命名卷，也不改变 Nginx 证书目录。

微信小程序仍是独立仓库，不部署到该服务器；`/home/ubuntu/MuseAI/frontend` 是管理端源码。

`.gitignore` 只控制未跟踪文件能否进入 Git，不是服务器端的部署过滤器。只要文件已经被
Git 跟踪，服务器 checkout 就会得到它；因此测试、文档和版本化数据仍会随仓库存在于服务器。
这部分体积很小，保留完整 checkout 比新增部署分支或制品系统更符合当前最小变化目标。

## 服务器路径保持不变

```text
/home/ubuntu/MuseAI/
├── .git/                         # 直接 fetch/checkout 与精确回退
├── .venv/                        # 服务器重建，不提交
├── .env                          # 生产配置和密钥，不提交
├── backend/                      # 后端源码、迁移和测试
├── frontend/                     # 管理端源码；dist/node_modules 不提交
├── data/                         # 版本化 CSV 模板与权威快照
├── deploy/                       # 去敏 systemd/Nginx/备份模板
├── docker/                       # Elasticsearch 构建定义
├── docker-compose.yml
├── logs/                         # 运行日志，不提交
└── scripts/                      # 导入和维护脚本

/home/ubuntu/museai-data/exhibit-images/   # 上传图片，不提交
/home/ubuntu/museai-backups/               # 数据库/图片备份，不提交
/home/ubuntu/museai-config-backups/        # 配置/发布记录，不提交
/home/ubuntu/.local/bin/uv                  # 直接部署工具，可重建但当前必须保留
/home/ubuntu/.local/share/uv/python/        # 当前 .venv 依赖的 Python 运行时
/home/ubuntu/.nvm/                          # 管理端在服务器构建时使用的 Node/npm 工具链
/home/ubuntu/.ssh/                          # 部署账号访问远端仓库所需配置
/var/www/museai-admin/                     # 管理端线上构建产物
/etc/systemd/system/museai-backend.service # 当前后端启动单元
/etc/logrotate.d/museai                    # 安装后由系统管理的日志轮转配置
/etc/nginx/conf.d/museai-*.conf            # 线上 Nginx 配置
/etc/nginx/ssl/museai/                     # 证书和私钥
/etc/letsencrypt/                          # Certbot 管理证书
/var/lib/docker/volumes/museai_*_data/     # PostgreSQL/Redis/Elasticsearch
```

## 应进入 Git 的内容

- 后端与管理端源码、Alembic 迁移、部署脚本和测试。
- `uv.lock`、`frontend/package-lock.json` 及以后实际 npm 项目的 lockfile。
- `.env.example` 和去敏后的 systemd、Nginx、logrotate 模板。
- `data/museum_template` 的统一格式模板。
- 获得提交授权、无个人信息的馆方正式 `halls.csv`、`exhibits.csv`、路线和地图元数据。
- 人格、提示模板、建议条等可复现业务输入。

真实数据不应被全局 `*.csv` 或 `*.xlsx` 规则忽略。操作员临时整理文件统一放到
`data/local-imports/`，该目录不提交；校验完成的权威快照再复制到明确的版本化数据目录提交。
若馆方数据没有进入公开仓库的授权，应改用私有数据仓库或受控上传，不得为了自动部署强行提交。

## 必须留在服务器且不得进入 Git 的内容

- `/home/ubuntu/MuseAI/.env` 及任何 `.env.local`、`.env.production` 等真实环境文件。
- `/etc/nginx/ssl`、`/etc/letsencrypt` 下的证书和私钥。
- Docker 数据卷中的数据库、Redis 状态和 Elasticsearch 索引/embedding。
- `/home/ubuntu/museai-data/exhibit-images` 中由管理端上传的图片。
- 应用、Nginx、journal 和 Docker 运行日志。
- 数据库、图片、配置和发布回退备份。
- 管理员密码哈希、游客会话、对话、报告等数据库运行记录。
- `.venv`、`node_modules`、`dist`、缓存、字节码和测试临时文件。
- 部署账号 SSH 配置、uv/uv Python 运行时，以及管理端在服务器构建时使用的 NVM/Node/npm 工具链。

固定且可公开使用的正式图片可以后续单独采用对象存储、带校验和的资产包或 Git LFS；不能把
管理端实时上传目录直接纳入 Git。

## `.gitignore` 边界

- 环境文件、证书/私钥、SQLite 文件、数据库与图片备份、上传目录和运行日志必须忽略。
- `frontend/dist`、`node_modules`、Python 虚拟环境及测试缓存属于可重建产物。
- `data/local-imports` 和 Excel 临时锁文件忽略；版本化 museum CSV 不忽略。
- `package-lock.json` 不做全局忽略，保证 npm 构建可复现。
- `docs/reference/private` 保持私密；可公开来源说明和数据字典允许跟踪。
- 已经被 Git 跟踪的生成物必须通过提交移除，仅新增 ignore 规则不会自动取消跟踪。

禁止在生产 checkout 执行 `git clean -fdx` 或 `git clean -fdX`。这些命令会删除被有意保留的
`.env`、`.venv`、日志和管理端构建依赖。清理只能针对已经核验过的精确路径逐项进行。

## 直接拉取部署流程

唯一权威命令和完整回退记录流程见
[小程序内容维护指南：生产部署和验收](./miniapp-content-maintenance.md#7-生产部署和验收)，本文件不再复制一套可能漂移的执行步骤。

该流程仍是服务器直接获取提交，但固定以下安全门禁：

- fetch 后解析并记录目标分支的精确 SHA，而不是无条件跟随可变分支执行普通 `git pull`。
- 切换前检查目标 tree 不得跟踪 `.env`、`.venv`、日志、上传目录、证书目录、管理端
  `dist/node_modules` 等服务器本地路径。
- 使用 `git switch --no-overwrite-ignore --detach <目标 SHA>`，目标提交与服务器 ignored 文件
  冲突时直接失败，不能静默覆盖。
- 先停止后端并确认 inactive，之后才能 `uv sync --frozen`、执行迁移并重新启动；不得修改运行中
  进程正在使用的 `.venv`。
- 如果管理端源码有变化，当前仍在服务器使用保留的 NVM/Node/npm 工具链按 lockfile 干净构建，
  再发布到 `/var/www/museai-admin`；不能依赖 checkout 中长期残留的旧 `frontend/dist`。

## 数据和证书更新

证书更新只发生在 Nginx/Certbot 管理目录，并在 `nginx -t` 后 reload，不进入 Git。

正式数据更新采用：统一 CSV/XLSX → 本地校验 → 可公开权威 CSV 提交 → 服务器 fetch 精确提交
→ dry-run → 正式导入 → 索引校验。数据库和 Elasticsearch 中的结果是运行状态，不反向提交 Git。
上传图片继续写入仓库外的持久目录，并与数据库备份作为同一批次回退资产。

因此服务器本地变化并不只有证书：`.env`、Docker 数据卷、上传图片、日志、备份和管理端构建
产物也必须长期保留；只有可复现且允许公开的真实数据源文件应该随 Git 更新。
