# 2026-08-10 main 合并与生产部署

## 目标

- 将 `codex/data-driven-miniapp-framework` 合并到后端 `main`。
- 验证 main 合并树后推送 `origin/main`。
- 服务器从 `origin/main` 获取精确 SHA，完成可回退部署与健康检查。

## 基线

- 合并前 `origin/main`：`1310b9955db2ba56059f9a158307a84aa2a6db78`。
- 功能分支与服务器当前 checkout：`baea8f8d8fa4d493eb298a85138cca06cb64d799`。
- 在线 fetch 后确认 main 没有独有提交，是功能分支的祖先，分叉计数为 `0 / 20`。
- 本地 main 已使用 `git merge --ff-only` 快进到 `baea8f8`，合并树与功能分支完全一致。
- 服务器预检：工作树干净，后端 PID `1312984`，内外网 readiness healthy，数据库和代码迁移 head 均为 `20260809_trusted_hall_chat_history`。

## 发布边界

- 权威部署来源从功能分支切换为 `origin/main`，仍采用 fetch、精确 SHA 与 detached checkout。
- 生产 `.env`、证书、Docker 卷、上传图片、日志和备份不得被提交或覆盖。
- 本次部署必须新建发布记录，以服务器现场 HEAD `baea8f8` 为 `OLD_SHA`；不得复用旧发布指针。
- 禁止 `git clean -fdx/-fdX`，禁止无条件 `git pull`。

## 当前步骤

1. 已将权威发布来源改为 `origin/main`。
2. 仓库外全新虚拟环境已完成依赖安装与导入；变更范围 65 个 Python 文件 Ruff 通过。
3. Alembic 为单一 `20260809_trusted_hall_chat_history (head)`；两套数据 dry-run 分别为 9 厅/0 展品和 9 厅/46 展品。
4. 完整后端回归 `1590 passed, 23 skipped, 9 warnings`。全仓 Ruff 的 27 项失败均位于合并 diff 外，是旧 main 已有格式问题，不作为本次回归阻断。
5. `origin/main` 已普通快进推送至 `b05c211f3668fc2a606c4caf3e0131ac09fe3f77`，未强推。
6. 服务器已从 `origin/main` checkout 精确 `b05c211`；相对原服务器 `baea8f8` 仅发布文档变化，因此未重启服务，MainPID 保持 `1312984`、NRestarts 为 0。
7. 发布记录为 `/home/ubuntu/museai-config-backups/release_20260810T160618Z.env`；数据库备份为 `/home/ubuntu/museai-backups/museai_20260811_000619_062350367.sql.gz`，SHA-256 `c63c99492e91c8f5a2fdec6a085901bf2a155ff0aa3cc7aa1bf80d4e8ef4a0a4`；图片备份为 `/home/ubuntu/museai-backups/exhibit-images_baea8f8d8fa4d493eb298a85138cca06cb64d799_20260810T160618Z.tar.gz`，SHA-256 `77d673e07aa7c5b512affec9facf471829e44a13e6a1df9acfcb8a9dc6267b19`。
8. 迁移 head、依赖、应用导入、Docker 健康、8000/3000 端口边界和内外网 readiness 均通过。首次日志检查的 ISO 时间格式不被 `journalctl` 接受，随后使用服务器本地时间重查并追加纠正记录，错误计数为 0。
9. 本地验证用临时虚拟环境和 pytest basetemp 已删除；默认 `.venv` 在首次刷新失败后已通过 `uv sync --frozen --extra dev` 修复，`uv pip check` 与应用导入通过。
