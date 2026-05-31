# Stage 10A — AI 响应慢 / 答非所问 诊断报告

> 生成于 Stage 10A 真机测试后。黑盒探针直接打线上 `chat/stream` API 实测。
> 结论：**问题 1（答非所问）和问题 2（慢）都在后端 LLM 层，前端无法修复。**

## 实测数据（同一问题、同一管道，唯一变量＝DeepSeek 上下文缓存状态）

| 问题 | 冷启动 first_token | 缓存命中 first_token |
|------|------------------|--------------------|
| Q1「这个展厅主要展示哪些类型的文物？」 | 126s / 36s | — |
| Q2「半坡的石器和骨器是做什么用的？」 | 55s | **2.8s** |

**关键证据**：Q2 缓存命中时整轮 **2.8 秒**完成。问题、检索、prompt 完全一样，
唯一差别是 DeepSeek KV 缓存是否命中。→ **瓶颈 100% 在 LLM 调用本身，不在 RAG 检索。**

## 三个根因

### 根因 A：thinking 模式开启（问题 2 主因）
- 短事实问答的 first_token 高达 36–126s，是「推理 token 先生成、再吐正文」的典型特征。
- `done` 事件里没有 usage 字段，无法直接读 reasoning_tokens，但延迟曲线已是铁证。
- **修复**：关闭 thinking。见下方代码方案。预计冷启动 first_token 从 ~40s 降到 ~3-8s。

### 根因 B：DeepSeek 上下文缓存未被刻意利用
- 缓存命中可把延迟打到 1/15（55s→2.8s）。
- 当前每次请求 system prompt 前缀不稳定（buildStyledPrompt 把展厅/风格/历史拼在最前），
  导致前缀 hash 经常变化，缓存命中率低。
- **修复方向**：把**固定不变的内容（persona system prompt、格式/语气约束）放在 messages 最前**，
  把**多变内容（用户问题、检索上下文）放在最后**。DeepSeek 自动对最长公共前缀做缓存。
  这是后端 `tour_chat_service.py` 拼 messages 顺序的调整。

### 根因 C：rag_step 事件未下发（问题 2 体感更差）
- 探针收到的 `rag_step` 列表为空 → 前端 6 步进度条永远不亮 → 用户面对纯白屏空等。
- 需确认后端是否真的 emit rag_step，还是 stage9 的 skip_generate 把节点事件一起跳过了。

### 问题 1（答非所问）与上面的关系
- 已通过 Stage 10A 建议条改造规避：只保留实测能答的题目。
- 残留的「答非所问」本质是 RAG 检索召回了错误 chunk。属于后端检索质量，
  需后端调 rerank 阈值 / chunk 切分，前端只能继续约束提问范围。

## 推荐后端修改（需你确认后再改 backend/）

### 1. 关闭 thinking（最高优先级，直接解决问题 2）

`backend/backend/app/infra/providers/llm.py` —
`OpenAICompatibleProvider.generate()` 和 `generate_stream()` 的 create 调用加：
```python
extra_body={"thinking": {"type": "disabled"}}
```

`backend/backend/app/infra/langchain/__init__.py` —
`create_llm()` 的 `ChatOpenAI(...)` 加：
```python
model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}}
```

### 2.（可选）显式 max_tokens 限制，防止超长输出
`llm.py` create 调用加 `max_tokens=800`（或读 settings.LLM_MAX_TOKENS）。

### 3.（可选）temperature=0.5，事实问答更稳定一致。

### 4. 排查 rag_step 是否下发
检查 `tour_chat_service._stream_rag()` 在 skip_generate=True 路径下是否仍
`yield sse_tour_event("rag_step", ...)`；若没有，补上让前端进度条可见。

## 已在前端完成（本 stage）
- 问题 3（iOS 闪烁）+ 问题 4（转圈卡死）：onboarding/persona-reveal 改用 redirectTo +
  非响应式 _navigating 守卫 + onShow 重置 loading。
- 建议条全部改为实测可答题目（见 store/tour.js _HALL_SUGGEST_TEMPLATES）。
