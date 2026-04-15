# 半坡博物馆 AI 导览游客流程设计文档

> 日期: 2026-04-15
> 状态: Draft
> 方案: 独立导览模式（方案A）

## 1. 概述

### 1.1 目标

为 MuseAI 博物馆 AI 导览系统实现完整的游客导览流程，包括：

1. **引导问卷**：3 道选择题了解游客游览需求
2. **身份导览**：3 种导览身份（考古队长/半坡原住民/历史老师）影响 RAG 生成风格
3. **展厅选择与导览**：2 个展厅的线性导览
4. **展品交互**：展品介绍 + 深入探索/下一个展品的引导循环
5. **游览报告**：游览统计、身份标签、五型图、游览一句话

### 1.2 关键决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 目标平台 | 现有 Vue 3 + Element Plus Web 前端 | 复用现有基础设施，降低开发成本 |
| RAG 集成 | 问卷结果同时影响前端展示和 RAG 生成 | 完整个性化体验 |
| 语音功能 | 后续迭代 | 降低首版复杂度 |
| 报告存储 | PostgreSQL 持久化 | 登录用户可回顾历史报告 |
| 展品数据 | 扩展现有 exhibits 表 | 复用基础数据，新增结构性字段 |
| 讲解词生成 | LLM 动态生成 | 灵活性高，无需写死讲解词 |
| 实现范围 | 全量实现 | 一次性交付完整体验 |

### 1.3 实现方案

采用**方案 A：独立导览模式**，在现有应用中新增 `/tour` 路由，拥有专属布局和线性流程控制器，与现有聊天/策展人功能解耦。

## 2. 整体架构与流程

### 2.1 导览流程状态机

```
ONBOARDING ──(完成3道选择题)──> OPENING ──(阅读开场白)──> HALL_SELECT ──(选择展厅)──>
HALL_INTRO ──(展厅介绍)──> EXHIBIT_TOUR ──(展品交互循环)──>
HALL_COMPLETE ──(展厅完成)──> [HALL_SELECT | TOUR_REPORT]
```

| 阶段 | 描述 | 关键数据 |
|------|------|---------|
| `ONBOARDING` | 3 道选择题问卷 | interest_type(A/B/C), persona(A/B/C), assumption(A/B/C) |
| `OPENING` | 根据 persona 展示开场白 | persona 对应的开场白 |
| `HALL_SELECT` | 选择展厅 | 可选展厅列表 |
| `HALL_INTRO` | 根据 persona 展示展厅讲解词 | persona + hall 对应的讲解词 |
| `EXHIBIT_TOUR` | 展品交互核心循环 | 当前展品、展品列表、交互事件 |
| `HALL_COMPLETE` | 当前展厅所有展品完成 | 展厅停留时间、展品交互统计 |
| `TOUR_REPORT` | 游览报告展示 | 聚合统计数据、五型图、标签、一句话 |

### 2.2 展品交互子循环

```
EXHIBIT_INTRO ──(AI介绍展品)──> EXHIBIT_INTERACT ──(用户提问/选择)──>
  ├── 深入了解 → EXHIBIT_INTERACT (继续对话)
  ├── 下一个展品 → EXHIBIT_INTRO (下一个展品)
  └── 展厅完成 → HALL_COMPLETE
```

### 2.3 路由结构

```
/tour                    → TourView (导览主容器)
/tour?step=onboarding    → OnboardingQuiz
/tour?step=opening       → OpeningNarrative
/tour?step=hall-select   → HallSelect
/tour?step=tour          → ExhibitTour
/tour?step=report        → TourReport
```

使用查询参数而非嵌套路由，因为导览是线性流程。

### 2.4 前端组件层级

```
TourView.vue (导览主容器)
├── OnboardingQuiz.vue (引导问卷)
├── OpeningNarrative.vue (开场白)
├── HallSelect.vue (展厅选择)
├── ExhibitTour.vue (展厅导览+展品交互)
│   ├── HallIntro.vue (展厅介绍)
│   ├── ExhibitIntro.vue (展品介绍)
│   ├── ExhibitChat.vue (展品对话，复用SSE流式)
│   └── ExhibitNavigator.vue (深入/下一个导航)
└── TourReport.vue (游览报告)
    ├── TourStats.vue (游览统计)
    ├── IdentityTags.vue (身份标签)
    ├── RadarChart.vue (五型图)
    └── TourOneLiner.vue (游览一句话)
```

## 3. 数据模型

### 3.1 新增表：`tour_sessions`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID (PK) | 导览会话 ID |
| `user_id` | UUID (FK→users, nullable) | 登录用户 ID，游客为 null |
| `guest_id` | VARCHAR(64) | 游客 ID（格式：guest-{uuid}） |
| `interest_type` | VARCHAR(1) | 兴趣方向：A=生存技术/B=符号艺术/C=社会结构 |
| `persona` | VARCHAR(1) | 导览身份：A=考古队长/B=半坡原住民/C=历史老师 |
| `assumption` | VARCHAR(1) | 初始假设：A=平等年代/B=荒野求生/C=阶级雏形 |
| `current_hall` | VARCHAR(50) | 当前展厅 slug |
| `current_exhibit_id` | UUID (FK→exhibits, nullable) | 当前展品 ID |
| `visited_halls` | JSON | 已参观展厅列表 |
| `visited_exhibit_ids` | JSON | 已参观展品 ID 列表 |
| `status` | VARCHAR(20) | 状态：onboarding/opening/touring/completed |
| `started_at` | TIMESTAMP | 导览开始时间 |
| `completed_at` | TIMESTAMP | 导览完成时间 |
| `created_at` | TIMESTAMP | 创建时间 |

### 3.2 新增表：`tour_events`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID (PK) | 事件 ID |
| `tour_session_id` | UUID (FK→tour_sessions) | 导览会话 ID |
| `event_type` | VARCHAR(30) | 事件类型：exhibit_view/exhibit_question/exhibit_deep_dive/hall_enter/hall_leave |
| `exhibit_id` | UUID (FK→exhibits, nullable) | 关联展品 ID |
| `hall` | VARCHAR(50, nullable) | 关联展厅 |
| `duration_seconds` | INTEGER | 停留时长（秒） |
| `metadata` | JSON | 附加数据（如提问内容、深入主题等） |
| `created_at` | TIMESTAMP | 事件时间 |

### 3.3 新增表：`tour_reports`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID (PK) | 报告 ID |
| `tour_session_id` | UUID (FK→tour_sessions, unique) | 导览会话 ID |
| `total_duration_minutes` | FLOAT | 总游览时长 |
| `most_viewed_exhibit_id` | UUID (FK→exhibits) | 最关注展品 |
| `most_viewed_exhibit_duration` | INTEGER | 最关注展品停留秒数 |
| `longest_hall` | VARCHAR(50) | 停留最长的展厅 |
| `longest_hall_duration` | INTEGER | 最长展厅停留秒数 |
| `total_questions` | INTEGER | 总提问次数 |
| `total_exhibits_viewed` | INTEGER | 总参观展品数 |
| `ceramic_questions` | INTEGER | 陶器相关提问次数 |
| `identity_tags` | JSON | 身份标签列表 |
| `radar_scores` | JSON | 五型图分数 |
| `one_liner` | TEXT | 游览一句话 |
| `report_theme` | VARCHAR(20) | 报告主题：archaeology/village/homework |
| `created_at` | TIMESTAMP | 创建时间 |

### 3.4 扩展 `exhibits` 表

仅新增结构性字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `hall` | VARCHAR(50) | 展厅 slug（relic-hall / site-hall） |
| `display_order` | INTEGER | 展厅内展示顺序 |
| `next_exhibit_id` | UUID (FK→exhibits, nullable) | 推荐的下一个展品 |

讲解词和推荐语由 LLM 根据展品基础数据 + 身份人设动态生成，不存储在数据库中。

### 3.5 新增领域实体

```python
class TourSession:
    id: TourSessionId
    user_id: UserId | None
    guest_id: str | None
    interest_type: str  # A/B/C
    persona: str        # A/B/C
    assumption: str     # A/B/C
    current_hall: str | None
    current_exhibit_id: ExhibitId | None
    visited_halls: list[str]
    visited_exhibit_ids: list[str]
    status: str
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

class TourEvent:
    id: TourEventId
    tour_session_id: TourSessionId
    event_type: str
    exhibit_id: ExhibitId | None
    hall: str | None
    duration_seconds: int
    metadata: dict
    created_at: datetime

class TourReport:
    id: TourReportId
    tour_session_id: TourSessionId
    total_duration_minutes: float
    most_viewed_exhibit_id: ExhibitId
    most_viewed_exhibit_duration: int
    longest_hall: str
    longest_hall_duration: int
    total_questions: int
    total_exhibits_viewed: int
    ceramic_questions: int
    identity_tags: list[str]
    radar_scores: dict
    one_liner: str
    report_theme: str
    created_at: datetime
```

### 3.6 新增值对象

```python
TourSessionId = NewType('TourSessionId', str)
TourEventId = NewType('TourEventId', str)
TourReportId = NewType('TourReportId', str)
```

## 4. API 端点设计

### 4.1 导览 API（`/api/v1/tour`）

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/tour/sessions` | 创建导览会话（提交问卷结果） | 可选 |
| GET | `/tour/sessions/{id}` | 获取导览会话状态 | 可选 |
| PUT | `/tour/sessions/{id}` | 更新导览会话 | 可选 |
| POST | `/tour/sessions/{id}/events` | 记录导览事件（批量） | 可选 |
| GET | `/tour/sessions/{id}/events` | 获取导览事件列表 | 可选 |
| POST | `/tour/sessions/{id}/complete-hall` | 完成当前展厅 | 可选 |
| POST | `/tour/sessions/{id}/report` | 生成游览报告 | 可选 |
| GET | `/tour/sessions/{id}/report` | 获取游览报告 | 可选 |
| POST | `/tour/sessions/{id}/chat/stream` | 导览专属 SSE 流式对话 | 可选 |
| GET | `/tour/halls` | 获取导览可用展厅列表 | 无 |

### 4.2 导览专属聊天端点

`POST /tour/sessions/{id}/chat/stream` 与现有 `/chat/ask/stream` 的区别：

1. **系统提示注入**：自动注入导览身份人设、当前展厅、当前展品上下文
2. **事件追踪**：每次对话自动记录 `exhibit_question` 事件
3. **陶器提问检测**：关键词匹配判断是否为陶器相关提问
4. **展品上下文**：自动将当前展品信息加入检索范围

请求体：
```json
{
  "message": "这个人面鱼纹盆是做什么用的？",
  "exhibit_id": "uuid-of-exhibit"
}
```

SSE `done` 事件额外返回：
```json
{
  "event": "done",
  "data": {
    "trace_id": "...",
    "sources": [...],
    "is_ceramic_question": true,
    "suggested_actions": {
      "deep_dive_prompt": "你是否好奇人面鱼纹在其他陶器上也有出现？",
      "next_exhibit": {
        "id": "uuid",
        "name": "尖底瓶",
        "hint": "如果这件器物的数据你已经掌握，建议按照时间地层的演化顺序..."
      }
    }
  }
}
```

### 4.3 展厅数据端点

扩展现有端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/exhibits?hall=relic-hall&sort=display_order` | 按展厅筛选并排序 |
| GET | `/tour/halls` | 导览可用展厅列表（含描述、展品数量） |

## 5. 导览身份与 RAG 集成

### 5.1 系统提示架构

```
[导览身份人设] + [展厅上下文] + [展品上下文] + [游客初始假设] + [通用RAG指令]
```

### 5.2 身份人设提示

**A - 考古队长**：
> 你是一位严谨求实的考古队长，正在带领游客勘探西安半坡博物馆。你的叙事风格：引用硬核发掘数据和学术推论，用"我们""数据表明""地层学证据"等措辞。避免主观臆测，对不确定的内容标注"学术界尚有争议"。在推荐下一个展品时，强调工艺承接关系和地层演化顺序。

**B - 半坡原住民**：
> 你是一位穿越来的半坡村原住民，正在带远道而来的朋友参观你曾经生活的村落。你的叙事风格：以村民视角第一人称叙述，增强沉浸感，用"我""阿妈""我们部落""当年"等措辞。把展柜里的文物描述成你曾经使用或见过的日常用品。在推荐下一个展品时，用生活化的语言描述它的用途和故事。

**C - 历史老师**：
> 你是一位爱提问的历史老师，正在带领学生进行半坡博物馆的沉浸式游学。你的叙事风格：多提供不同观点并引导思考，用"同学们""想一想""你觉得呢"等措辞。每个知识点后抛出启发性问题。在推荐下一个展品时，设置悬念和对比思考任务。

### 5.3 展厅/展品上下文注入

通过 RAG 检索自动注入：
- 当前展厅名称和主题描述
- 当前展品的名称、描述、年代、类别等基础信息
- 游客已参观的展品列表（避免重复介绍）

### 5.4 游客初始假设关联

问题 3 的选择作为额外上下文注入，当讨论到社会结构、墓葬差异、贫富分化相关内容时，LLM 自然关联到游客的初始假设并引导反思。

### 5.5 RAG 流程

```
游客提问/到达展品
    ↓
TourChatService.ask_stream()
    ↓
构建系统提示 = persona_prompt + hall_context + exhibit_context + assumption_context
    ↓
RAG Agent (现有管道)
    ├── rewrite (查询重写，考虑展品上下文)
    ├── retrieve (RRF检索，优先当前展品相关文档)
    ├── rerank (重排序)
    ├── evaluate (质量评估)
    └── generate (生成回答，遵循persona风格)
    ↓
后处理：
    ├── 检测是否陶器相关提问
    ├── 生成深入引导提示
    └── 生成下一个展品推荐语
    ↓
SSE 流式返回
```

### 5.6 Prompt 模板

新增到 `prompts` 表：

| Prompt Key | 用途 | 关键变量 |
|------------|------|---------|
| `tour.opening` | 开场白生成 | persona, assumption |
| `tour.hall_intro` | 展厅介绍生成 | persona, hall_name, hall_description |
| `tour.exhibit_narrative` | 展品讲解生成 | persona, exhibit_name, exhibit_description |
| `tour.exhibit_deep_dive` | 展品深入引导 | persona, exhibit_name, visitor_question |
| `tour.exhibit_next_hint` | 下一个展品推荐语 | persona, current_exhibit, next_exhibit |
| `tour.report_one_liner` | 游览一句话生成 | persona, stats_summary |

## 6. 游览报告系统

### 6.1 报告生成流程

```
游客完成所有展厅
    ↓
POST /tour/sessions/{id}/report
    ↓
聚合 tour_events 数据
    ↓
计算五型图分数
    ↓
选择身份标签
    ↓
LLM 生成游览一句话
    ↓
持久化到 tour_reports
```

### 6.2 五型图评分规则

| 维度 | 计算方式 | B级 | A级 | S级 |
|------|---------|-----|-----|-----|
| 文明共鸣度 | 总游览时长 | <30min | 30-60min | >60min |
| 脑洞广度 | 提问次数 | <10 | 10-15 | >15 |
| 历史碎片收集度 | 参观展品数 | <5 | 5-10 | >10 |
| 半坡生活体验度 | 遗址展厅停留时间(分钟) | <10 | 10-20 | >20 |
| 彩陶审美力 | 陶器相关提问次数 | 0次=A | ≥1次=S | — |

分数映射：B=1, A=2, S=3。

### 6.3 身份标签选择逻辑

| 类别 | 标签池 | 选择规则 |
|------|--------|---------|
| 硬核求知类 | 史前细节显微镜、碎片重构大师、冷酷无情的地层勘探机 | 文明共鸣度S→地层勘探机，历史碎片收集度S→碎片重构大师，否则→史前细节显微镜 |
| 脑洞/趣味类 | 六千年前的干饭王、母系氏族社交悍匪、沉睡的部落大祭司 | 脑洞广度S→社交悍匪，半坡生活体验度S→部落大祭司，否则→干饭王 |
| 审美/文艺类 | 史前第一眼光、彩陶纹饰解码者、被文物选中的人 | 彩陶审美力S→彩陶纹饰解码者，文明共鸣度S→被文物选中的人，否则→史前第一眼光 |

### 6.4 游览一句话生成

通过 LLM 生成，输入统计数据和 persona 风格，从预设候选池中选取或生成新的。

候选池：
- 今天，我用AI唤醒了沉睡六千年的半坡先民
- 我的博物馆向导来自公元前4000年
- 没有文字的时代，他们把不朽的灵魂画在彩陶上
- 凝视人面鱼纹盆的瞬间，六千年的风从浐河吹进了现实
- 我们在泥土里寻找的不是瓦罐，而是六千年前祖宗的倒影
- 半坡一日游达成：确认过了，如果回到6000年前，我的手艺只配负责吃
- 懂了，六千年前的先民不内卷，每天研究怎么抓鱼和捏泥巴

### 6.5 报告视觉主题

| Persona | 标题 | 背景元素 |
|---------|------|---------|
| A（考古队长） | 你的半坡考古报告 | 考古卷轴、探方网格、地层剖面 |
| B（半坡原住民） | 半坡一日穿越体验 | 陶器纹饰、鱼纹符号、茅草纹理 |
| C（历史老师） | 半坡游学荣誉证书 | 作业本格子、红笔批注、印章 |

## 7. 前端组件与 Composable 设计

### 7.1 useTour.js Composable

```javascript
// 核心状态
const tourSession = ref(null)
const tourStep = ref('onboarding')
const currentHall = ref(null)
const currentExhibit = ref(null)
const hallExhibits = ref([])
const exhibitIndex = ref(0)
const tourEvents = ref([])
const exhibitStartTime = ref(null)
const streamingContent = ref('')
const suggestedActions = ref(null)

// 核心方法
createTourSession(interestType, persona, assumption)
selectHall(hallSlug)
enterExhibit(exhibitId)
sendTourMessage(message)
recordEvent(eventType, metadata)
completeHall()
generateReport()
```

### 7.2 新增路由

```javascript
{
  path: '/tour',
  name: 'tour',
  component: () => import('../views/TourView.vue'),
  meta: { requiresAuth: false }
}
```

### 7.3 组件设计

#### TourView.vue
- 管理导览阶段状态机
- 根据 tourStep 渲染对应子组件
- 全屏沉浸式布局（隐藏 Header 和 Sidebar）
- 顶部显示导览身份标识和进度条

#### OnboardingQuiz.vue
- 3 道选择题逐题展示
- 每题选择后自动进入下一题，带过渡动画
- 半坡主题视觉设计
- 最后一题完成后自动创建导览会话

#### OpeningNarrative.vue
- 根据 identity 展示对应开场白
- 打字机效果逐字展示
- 底部"开始探索"按钮

#### HallSelect.vue
- 2 个展厅卡片
- 每个卡片含展厅名称、简介、展品数量

#### ExhibitTour.vue
- 三段式布局：顶部展厅信息 + 中部对话区 + 底部操作区
- 对话区复用 SSE 流式模式
- 底部操作区：文字输入框 + "深入了解"按钮 + "下一个展品"按钮
- AI 回答结束后显示建议操作卡片

#### TourReport.vue
- 根据 report_theme 切换视觉主题
- 顶部：报告标题 + 游览时长
- 中部：最关注展品 + 最长展厅
- 身份标签区：3 个标签卡片
- 五型图：Canvas 绘制的雷达图
- 游览一句话：大字展示
- 底部：小程序二维码占位

### 7.4 事件追踪机制

事件先缓存在前端 tourEvents 中，定期批量提交到后端（每 30 秒或切换展品时）。

```javascript
// 进入展品时
exhibitStartTime.value = Date.now()

// 离开展品时
const duration = Math.floor((Date.now() - exhibitStartTime.value) / 1000)
recordEvent('exhibit_view', { exhibit_id, duration_seconds: duration })

// 提问时
recordEvent('exhibit_question', { exhibit_id, question, is_ceramic_question })

// 深入了解时
recordEvent('exhibit_deep_dive', { exhibit_id, topic })
```

## 8. 后端服务层设计

### 8.1 新增服务

| 服务 | 职责 |
|------|------|
| `TourSessionService` | 导览会话 CRUD、状态管理 |
| `TourEventService` | 导览事件记录与查询 |
| `TourChatService` | 导览专属聊天（SSE 流式 + 身份人设注入） |
| `TourReportService` | 游览报告生成（聚合计算 + LLM 一句话） |

### 8.2 TourChatService 核心逻辑

```python
class TourChatService:
    async def ask_stream(self, session_id, message, exhibit_id=None):
        session = await self.get_session(session_id)
        persona_prompt = self._build_persona_prompt(session.persona)
        hall_context = self._build_hall_context(session.current_hall)
        exhibit_context = await self._build_exhibit_context(exhibit_id)
        assumption_context = self._build_assumption_context(session.assumption)

        system_prompt = f"{persona_prompt}\n{hall_context}\n{exhibit_context}\n{assumption_context}"

        async for event in self.rag_agent.stream(message, system_prompt=system_prompt):
            yield event

        # 后处理
        is_ceramic = self._detect_ceramic_question(message)
        await self._record_question_event(session_id, exhibit_id, message, is_ceramic)

        # 异步生成建议操作
        suggested = await self._generate_suggested_actions(session, exhibit_id, is_ceramic)
        yield {"event": "suggested_actions", "data": suggested}
```

### 8.3 TourReportService 核心逻辑

```python
class TourReportService:
    async def generate_report(self, session_id):
        events = await self.event_service.get_events(session_id)
        session = await self.session_service.get_session(session_id)

        stats = self._aggregate_stats(events, session)
        radar_scores = self._calculate_radar_scores(stats)
        identity_tags = self._select_identity_tags(radar_scores)
        one_liner = await self._generate_one_liner(session.persona, stats)

        report = TourReport(
            tour_session_id=session_id,
            report_theme=self._get_theme(session.persona),
            identity_tags=identity_tags,
            radar_scores=radar_scores,
            one_liner=one_liner,
            **stats
        )
        await self.report_repo.save(report)
        return report
```

## 9. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 导览会话不存在 | 返回 404，前端重定向到 /tour |
| 游客会话过期 | 返回 410，前端提示重新开始 |
| SSE 连接断开 | 自动重连，从最后一条消息继续 |
| LLM 生成失败 | 降级到预设模板回答 |
| 报告生成失败 | 重试一次，仍失败则返回基础统计（无一句话） |
| 展品数据缺失 | 跳过该展品，继续下一个 |

## 10. 测试策略

| 层级 | 覆盖范围 |
|------|---------|
| 单元测试 | TourSessionService、TourReportService 的业务逻辑、五型图计算、标签选择 |
| 契约测试 | 所有 /tour API 端点的请求/响应格式 |
| 集成测试 | 导览聊天 SSE 流式 + 身份人设注入 |
| E2E 测试 | 完整导览流程：问卷→开场白→展厅→展品→报告 |
