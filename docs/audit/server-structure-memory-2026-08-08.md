# 生产服务器文件结构与内存审计

审计时间：2026-08-08（Asia/Shanghai）。本清单完整覆盖根分区一级结构和 MuseAI 源码目录；
`.git`、`.venv`、`node_modules`、构建产物、日志和缓存只统计大小，不展开其中每个生成文件。
审计未读取 `.env`、SSH 私钥、认证缓存或其他密钥内容。

## 服务器根结构

```text
/
├── .Recycle_bin/   4 KiB
├── boot/           259 MiB
├── data/           4 KiB
├── dev/            设备文件系统
├── etc/            21 MiB
├── home/           7.0 GiB
│   └── ubuntu/
│       ├── MuseAI/             后端与管理端部署项目
│       ├── MyWeb/              另一独立站点，不属于 MuseAI
│       ├── museai-backups/     PostgreSQL 备份
│       ├── deploy-logs/        另一站点部署日志
│       └── 用户工具与缓存目录
├── media/          4 KiB
├── mnt/            4 KiB
├── opt/            20 KiB
├── patch/          8 KiB
├── proc/           内核虚拟文件系统
├── root/           8.8 MiB
├── run/            运行时虚拟文件系统
├── snap/           36 KiB（挂载镜像另计）
├── srv/            4 KiB
├── sys/            内核虚拟文件系统
├── tmp/            13 MiB
├── usr/            4.9 GiB
├── var/            7.1 GiB（主要含 Docker 数据与系统状态）
├── www/            783 MiB（宝塔面板）
└── swapfile        2.0 GiB 文件存在，但当前未启用为 Swap
```

根分区为 99 GiB，已使用约 22 GiB（24%），可用约 73 GiB。

## `/home/ubuntu` 主要占用

| 路径 | 大小 | 说明 |
|---|---:|---|
| `.vscode-server` | 4.7 GiB | 远程 VS Code 运行时与扩展，是 home 最大项 |
| `.cache` | 576 MiB | 通用/包管理缓存 |
| `.nvm` | 455 MiB | Node 版本管理器 |
| `MyWeb` | 437 MiB | 与 MuseAI 无关的独立项目 |
| `MuseAI` | 表观约 578 MiB | 含虚拟环境、管理端依赖、Git 与源码；硬链接按父目录统计时占用会更低 |
| `.npm` | 266 MiB | npm 缓存 |
| `.local` | 171 MiB | 用户级工具与 Python/uv 资源 |
| `museai-backups` | 5.3 MiB | 当前 PostgreSQL 压缩备份 |

## MuseAI 项目结构

```text
/home/ubuntu/MuseAI
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── api/
│   │   │   └── admin/
│   │   ├── application/
│   │   │   ├── llm_trace/
│   │   │   ├── ports/
│   │   │   └── workflows/
│   │   ├── config/
│   │   ├── domain/
│   │   │   └── services/
│   │   ├── infra/
│   │   │   ├── cache/
│   │   │   ├── elasticsearch/
│   │   │   ├── langchain/
│   │   │   ├── postgres/
│   │   │   ├── providers/
│   │   │   ├── redis/
│   │   │   └── security/
│   │   └── observability/
│   ├── scripts/
│   └── tests/
│       ├── contract/
│       ├── e2e/
│       │   └── test_data/
│       ├── fixtures/
│       └── unit/
├── data/
│   ├── museum_template/       九厅可信空展品模板
│   └── museum_test_data/      46 条明确标记的多厅测试展品
├── deploy/                    systemd、Nginx、备份和日志轮转资产
├── docker/
│   └── elasticsearch/
├── docs/
│   ├── agent-runs/
│   ├── audit/
│   ├── logs/
│   ├── plans/
│   ├── reference/
│   ├── security/
│   └── superpowers/
├── frontend/                  后端仓库内的管理端 Web 客户端
│   ├── public/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── composables/
│       ├── constants/
│       ├── design-system/
│       ├── directives/
│       ├── router/
│       ├── styles/
│       ├── utils/
│       └── views/
├── logs/                      运行日志，未纳入源码结构
├── scripts/                   导入、管理员、初始化和质量检查脚本
├── .git/                      约 37 MiB
├── .venv/                    约 283 MiB
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
└── README.md / README_EN.md
```

当前提交共有 494 个 Git 跟踪文件、91 个跟踪目录。服务器上的这个 `frontend/` 是管理端；
微信小程序是独立仓库，不部署在该目录中。

## 8 GiB 内存归因

系统实际可识别 7.3 GiB。审计时约 1.9 GiB 为进程实际使用，约 5.1 GiB 为 Linux
文件页缓存和可回收内核缓存，`MemAvailable` 约 5.0 GiB，因此不是“只剩 260 MiB 可用”。

| 使用方 | 当前占用 | 说明 |
|---|---:|---|
| Elasticsearch 容器 | 约 693 MiB / 768 MiB | 最大 MuseAI 组件；约占容器限制 90%，但不是主机内存耗尽 |
| Docker 守护进程 `dockerd` | RSS 约 479 MiB | 管理全部容器；RSS 与容器统计不可简单相加 |
| MuseAI Uvicorn | RSS 约 216 MiB | 单 worker，符合 2C8G 部署方案 |
| 腾讯云安全/监控代理 | 约 180–200 MiB | `YDService`、`YDLive`、`barad_agent`、`tat_agent` 等 |
| 宝塔面板及任务进程 | 约 105 MiB | `BT-Panel`、`BT-Task` 等 |
| systemd-journald | RSS 约 67 MiB | 系统日志服务 |
| PostgreSQL 容器 | 约 56 MiB | 当前数据量较小 |
| Redis 容器 | 约 8 MiB | 当前缓存量较小 |
| 其他系统进程 | 数百 MiB | containerd、snapd、Nginx、内核服务和共享库等 |

Elasticsearch 容器百分比较高，后续批量导入继续串行执行并监控；主机本身仍有约 5 GiB
可用内存。服务器存在 2 GiB `/swapfile`，但 `free` 显示 Swap 为 0，说明尚未 `swapon`。

## 部署状态

- 代码：`6a3720e14ddbd127ee194d3d77b3f925fa55888d`。
- 数据库迁移：`20260808_remove_legacy_halls (head)`。
- 管理员：只有 `test@test.com` 为 `admin`；`admin@museai.local` 已降为 `user`，未删除。
- 测试展品：46 条启用，九厅分布为 6/5/5/5/5/5/5/5/5；46 条旧无来源记录均已停用。
- Elasticsearch：858 个测试分片、46 个来源，旧来源抽样计数为 0。
- 健康：本地与公网 API 正常，PostgreSQL、Elasticsearch、Redis 均为 healthy。
- 备份：`/home/ubuntu/museai-backups/museai_pre_test_import_20260808_164810.sql.gz`，
  SHA-256 `689896c85cd13d007c03049dc71c3d377a93f31754773f8a976183a1976517fe`。
