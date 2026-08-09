# 2026-08-10 报告页 422 与服务器存储整理

## 目标

- 定位并修复小程序打开报告前反复 `PATCH /tour/sessions/{id}` 返回 422 的问题。
- 完成自动化回归、提交、推送、生产部署与报告接口探针。
- 只读盘点服务器存储，给出运行资产、持久数据、日志、备份和临时文件的重排方案；未经用户批准不移动或删除文件。

## 仓库边界

- 后端：`E:\Proj\Museum_agent\MuseAI\backend`，分支 `codex/data-driven-miniapp-framework`。
- 小程序：`E:\Proj\Museum_agent\MuseAI\frontend`，唯一分支 `main`。
- 服务器：`/home/ubuntu/MuseAI` 是后端与管理端仓库；小程序仓库不部署在该目录。

## 当前证据

- 生产响应与日志已确认：九厅路线的每个 step 包含 `short`、`exhibitCount`、`exhibitCountKnown`，旧后端严格模型未声明，合计 27 条 `extra_forbidden`。报告 POST 未执行，会话本身健康。
- 两个本地仓库开始排查时均与各自远端同步且工作树干净。
- 生产服务此前部署于后端提交 `0909a7615604015bc2a7c394efa2c2a0af05d44a`。
- 后端已为三个明确字段补齐约束，未知字段仍拒绝；完整九厅 PATCH/GET 等值恢复、旧快照默认值、边界与严格拒绝契约共 66 项通过。
- 后端全量 `1590 passed, 23 skipped, 9 warnings`，scoped Ruff 和 `git diff --check` 通过。
- 小程序已抑制多个并发等待者重复发送同一失败快照，也覆盖 409 刷新版本后遇到 422 与飞行期间加入不同新状态；全部 16 组检查与 64 文件发布预检通过。
- 服务器存储只读盘点完成，方案写入 `docs/server-storage-layout.md`，未移动或删除文件。

## 当前步骤

1. 更新两仓库日志，分别提交并推送。
2. 按既有备份与 systemd 流程部署后端。
3. 执行生产九厅 PATCH→GET→报告探针并确认原 422 消失。
4. 记录生产 SHA、备份与探针结果；存储重排等待用户审批，不在本轮执行。

## 安全边界

- 不读取或输出 `.env`、API key、session token、私钥或备份正文。
- 不重置管理员密码，不修改生产数据。
- 存储盘点阶段不移动、不删除服务器文件。
