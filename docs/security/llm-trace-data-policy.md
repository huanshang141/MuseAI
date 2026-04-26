# LLM 调用追踪数据策略

## 1. 字段定义

`llm_trace_events` 表记录所有经系统发出的 LLM 调用，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `call_id` | String(64) | 调用唯一标识，全局唯一 |
| `request_id` | String(64) | HTTP 请求 ID（可选） |
| `trace_id` | String(64) | 分布式追踪 ID（可选） |
| `source` | String(64) | 调用来源（如 chat_stream, rag_generate） |
| `endpoint_method` | String(10) | HTTP 方法（可选） |
| `endpoint_path` | String(255) | HTTP 路径（可选） |
| `actor_type` | String(20) | 调用者类型（如 user, system） |
| `actor_id` | String(64) | 调用者 ID |
| `session_type` | String(20) | 会话类型（如 chat, tour） |
| `session_id` | String(64) | 会话 ID |
| `provider` | String(64) | LLM 提供商（如 openai-compatible, langchain-openai） |
| `base_url` | Text | LLM API 基础 URL（脱敏后） |
| `model` | String(128) | 模型名称 |
| `request_payload_masked` | JSON | 请求负载（脱敏后） |
| `response_payload_masked` | JSON | 响应负载（脱敏后） |
| `request_readable` | Text | 请求可读摘要 |
| `response_readable` | Text | 响应可读摘要 |
| `prompt_tokens` | Integer | 输入 Token 数 |
| `completion_tokens` | Integer | 输出 Token 数 |
| `total_tokens` | Integer | 总 Token 数 |
| `started_at` | DateTime | 调用开始时间 |
| `ended_at` | DateTime | 调用结束时间 |
| `duration_ms` | Integer | 调用耗时（毫秒） |
| `status` | String(20) | 调用状态（success / error） |
| `error_type` | String(128) | 错误类型（仅 error 时） |
| `error_message_masked` | Text | 错误信息（脱敏后） |
| `created_at` | DateTime | 记录创建时间 |

## 2. 脱敏策略

所有 LLM 调用追踪数据在写入数据库前必须经过脱敏处理，确保敏感信息不被持久化存储。

### 2.1 JSON 脱敏规则

- **敏感 Key 匹配**：当 JSON key 包含以下关键词时，值替换为 `[REDACTED]`
  - `api_key`, `token`, `secret`, `authorization`, `password`, `access_token`, `refresh_token`, `id_token`, `auth`, `key`, `private_key`, `client_secret`
- **递归处理**：对嵌套的 dict 和 list 递归应用脱敏规则
- **字符串内嵌**：对 JSON 中所有字符串值应用文本脱敏规则

### 2.2 文本脱敏规则

- **邮箱**：替换为 `[REDACTED]`
- **手机号**：1 开头的 11 位数字替换为 `[REDACTED]`
- **Bearer Token**：`Bearer xxx` 格式替换为 `Bearer [REDACTED]`
- **JWT**：`eyJ...` 格式替换为 `[REDACTED]`

### 2.3 URL 脱敏规则

- URL query 参数中的敏感 key（`api_key`, `token`, `secret`, `password`, `auth`, `key`）对应值替换为 `[REDACTED]`

### 2.4 失败兜底

- 脱敏过程发生异常时，返回 `[MASKING_FAILED]` 占位符，**绝不回退为原文**

## 3. 保留周期

| 环境 | 默认保留期 | 说明 |
|------|-----------|------|
| 开发环境 | 30 天 | 可按需调整 |
| 生产环境 | 90 天 | 建议通过定时任务清理 |

清理脚本：`scripts/cleanup_llm_traces.py`

```bash
# 清理 30 天前的记录
python scripts/cleanup_llm_traces.py --days 30

# 预览模式（不实际删除）
python scripts/cleanup_llm_traces.py --days 30 --dry-run
```

建议配合 cron 或其他定时任务系统定期执行。

## 4. 数据访问权限

- **API 访问**：仅 `admin` 角色用户可通过 `/api/v1/admin/llm-traces` 接口访问
- **前端页面**：仅管理员可在侧边栏看到"LLM 调用追踪"入口
- **数据库直连**：遵循 PostgreSQL 最小权限原则，应用账号仅拥有必要的 CRUD 权限
- **非管理员**：访问 API 返回 403 Forbidden

## 5. 旁路原则

- 追踪记录失败**不得**影响主业务流程
- Recorder 内部所有异常仅记录日志，不向上抛出
- 数据库不可用时，追踪功能静默降级
