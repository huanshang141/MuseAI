# Tour Workspace Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `/tour` 改造为“仅在 `tourStep='tour'` 启用的工作台形态”，恢复全站顶部导航，并落地四个二级标签、左侧混合功能区、展品模板补全、风格注入设置和移动端适配。

**Architecture:** 保留 `useTour` 作为导览业务状态机与 API 通讯层，新增 `useTourWorkbench` 作为纯前端工作台状态层；`TourView` 仅负责步骤分发，`TourWorkspace` 承担 `tour` 阶段 UI 编排。视觉沿用全站 design tokens，以浅色主基调为主，消息区局部沉浸，不再全页独占深色壳层。

**Tech Stack:** Vue 3 (`<script setup>`), Vue Router 4, Element Plus 2.13.6, Vite, Vitest

**Spec:** `docs/superpowers/specs/2026-04-29-tour-workspace-redesign-design.md`

---

## Scope Check

本次计划只覆盖一个子系统：`/tour` 前端交互与布局重构。不会触及后端协议、数据库、导览状态机核心流程。该范围可在单一计划内闭环交付。

---

## File Structure (Locked Before Implementation)

### Create

- `frontend/src/components/tour/TourWorkspace.vue`
- `frontend/src/components/tour/workspace/TourSecondaryTabs.vue`
- `frontend/src/components/tour/workspace/TourWorkspaceSidebar.vue`
- `frontend/src/components/tour/workspace/TourSessionPanel.vue`
- `frontend/src/components/tour/workspace/TourExhibitQuickView.vue`
- `frontend/src/components/tour/workspace/TourProgressPanel.vue`
- `frontend/src/components/tour/workspace/TourSettingsPanel.vue`
- `frontend/src/composables/useTourWorkbench.js`
- `frontend/src/composables/__tests__/useTourWorkbench.test.js`
- `frontend/src/components/tour/workspace/__tests__/TourSessionPanel.test.js`
- `frontend/src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js`
- `frontend/src/components/tour/workspace/__tests__/TourSettingsPanel.test.js`
- `frontend/src/components/tour/__tests__/TourViewWorkspaceGate.test.js`

### Modify

- `frontend/src/App.vue`
- `frontend/src/views/TourView.vue`
- `frontend/src/router/index.js`
- `frontend/src/components/layout/AppSidebar.vue`
- `frontend/src/styles/custom.css`
- `frontend/src/components/tour/ExhibitTour.vue`
- `frontend/src/components/tour/ExhibitChat.vue`

### Optional Create (if needed during implementation)

- `frontend/src/components/layout/sidebars/TourWorkspaceSidebar.vue`（若决定接入全局侧边栏分发）

---

## Implementation Chunks

## Chunk 1: App Shell Integration and Step Gating

### Task 1: 恢复 `/tour` 顶部导航并去除全屏独占逻辑

**Files:**
- Test: `frontend/src/components/tour/__tests__/TourViewWorkspaceGate.test.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/views/TourView.vue`

- [ ] **Step 1: 写失败测试，锁定 `/tour` 不再隐藏 AppHeader**

```js
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../../../App.vue'

it('keeps app header visible on /tour route', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/tour', component: { template: '<div>tour</div>' } }],
  })
  await router.push('/tour')
  await router.isReady()

  const wrapper = mount(App, {
    global: { plugins: [router], stubs: { AppHeader: true, AppSidebar: true, AuthModal: true } },
  })

  expect(wrapper.findComponent({ name: 'AppHeader' }).exists()).toBe(true)
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm run test -- --run src/components/tour/__tests__/TourViewWorkspaceGate.test.js`
Expected: FAIL，现状 `/tour` 分支隐藏 `AppHeader`

- [ ] **Step 3: 在 `App.vue` 删除 `isTourMode` 对 Header/Sidebar 的硬切断**

关键修改：

```js
const sidebarType = computed(() => route.meta?.sidebar ?? null)
const hasSidebar = computed(() => !!sidebarType.value)
```

```vue
<AppHeader
  :show-sidebar-toggle="isMobile && hasSidebar"
  @toggle-sidebar="toggleSidebarDrawer"
/>
```

- [ ] **Step 4: 在 `TourView.vue` 移除 `body.tour-mode` 相关逻辑与全屏样式**

删除：
- `document.body.classList.add/remove('tour-mode')`
- `body.tour-mode .app-header/.app-sidebar` 强制隐藏规则

保留：
- `restoreSession()`
- `setupBeforeUnload()`

- [ ] **Step 5: 运行测试验证通过**

Run: `cd frontend && npm run test -- --run src/components/tour/__tests__/TourViewWorkspaceGate.test.js`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.vue frontend/src/views/TourView.vue frontend/src/components/tour/__tests__/TourViewWorkspaceGate.test.js
git commit -m "feat(frontend): restore app shell on tour route and remove fullscreen isolation"
```

---

### Task 2: `tourStep` 分流：仅在 `tour` 阶段渲染新工作台

**Files:**
- Modify: `frontend/src/views/TourView.vue`
- Create: `frontend/src/components/tour/TourWorkspace.vue`
- Test: `frontend/src/components/tour/__tests__/TourViewWorkspaceGate.test.js`

- [ ] **Step 1: 写失败测试，锁定步骤分流行为**

```js
it('renders TourWorkspace only when tourStep is tour', async () => {
  // mock useTour with different tourStep values
  // assert TourWorkspace existence toggles correctly
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/tour/__tests__/TourViewWorkspaceGate.test.js`
Expected: FAIL，当前 `tourStep='tour'` 渲染的是旧 `ExhibitTour`

- [ ] **Step 3: 新建 `TourWorkspace.vue` 并在 `TourView.vue` 引入分流**

目标模板：

```vue
<OnboardingQuiz v-if="tourStep === 'onboarding'" />
<OpeningNarrative v-else-if="tourStep === 'opening'" />
<HallSelect v-else-if="tourStep === 'hall-select'" />
<TourWorkspace v-else-if="tourStep === 'tour'" />
<TourReport v-else-if="tourStep === 'report'" />
```

- [ ] **Step 4: 回归验证**

Run:
- `cd frontend && npm run test -- --run src/components/tour/__tests__/TourViewWorkspaceGate.test.js`
- `cd frontend && npm run test -- --run src/components/tour/__tests__/ExhibitTour.test.js`

Expected:
- 新 gate 测试 PASS
- `ExhibitTour` 旧测试如被下线则替换为 `TourWorkspace` 对应测试；若仍保留功能片段则通过

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/TourView.vue frontend/src/components/tour/TourWorkspace.vue frontend/src/components/tour/__tests__/TourViewWorkspaceGate.test.js
git commit -m "feat(frontend): gate tour workspace to tourStep phase"
```

---

## Chunk 2: Workbench State and Base Layout

### Task 3: 新增 `useTourWorkbench`（草稿、标签、偏好、风格注入）

**Files:**
- Create: `frontend/src/composables/useTourWorkbench.js`
- Test: `frontend/src/composables/__tests__/useTourWorkbench.test.js`

- [ ] **Step 1: 先写失败测试（默认值、持久化、模板与风格拼装）**

```js
it('buildStyledPrompt injects style hints above user message', () => {
  const { buildStyledPrompt } = useTourWorkbench()
  const result = buildStyledPrompt('介绍一下人面鱼纹彩陶盆', {
    answerLength: 'detailed', depth: 'deep', terminology: 'academic'
  })
  expect(result).toContain('回答长度')
  expect(result).toContain('介绍一下人面鱼纹彩陶盆')
})
```

```js
it('inserts exhibit template and keeps unsent draft', () => {
  const { chatDraft, insertTemplateForExhibit } = useTourWorkbench()
  insertTemplateForExhibit({ id: '1', name: '尖底瓶' }, 'intro')
  expect(chatDraft.value).toBe('介绍一下尖底瓶')
})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npm run test -- --run src/composables/__tests__/useTourWorkbench.test.js`
Expected: FAIL（composable 尚不存在）

- [ ] **Step 3: 实现最小可用 composable**

至少包含：

```js
const activeTab = ref('session')
const chatDraft = ref('')
const uiPreferences = ref({ fontScale: 'md', messageDensity: 'comfortable', autoScroll: true, showQuickPrompts: true, rememberDraft: true })
const stylePreferences = ref({ answerLength: 'balanced', depth: 'standard', terminology: 'plain', enabled: true })
const ttsPreferences = ref({ voice: 'female_warm', speed: '1x', autoPlay: false })

function insertTemplateForExhibit(exhibit, key) { /* ... */ }
function buildStyledPrompt(rawInput, style) { /* ... */ }
```

- [ ] **Step 4: 运行测试确保通过**

Run: `cd frontend && npm run test -- --run src/composables/__tests__/useTourWorkbench.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useTourWorkbench.js frontend/src/composables/__tests__/useTourWorkbench.test.js
git commit -m "feat(frontend): add tour workbench state and prompt style injection"
```

---

### Task 4: 搭建工作台骨架（左侧混合功能区 + 右侧标签面板）

**Files:**
- Create: `frontend/src/components/tour/workspace/TourSecondaryTabs.vue`
- Create: `frontend/src/components/tour/workspace/TourWorkspaceSidebar.vue`
- Modify: `frontend/src/components/tour/TourWorkspace.vue`
- Test: `frontend/src/components/tour/workspace/__tests__/TourSessionPanel.test.js`（先做最小挂载测试）

- [ ] **Step 1: 写失败测试，锁定布局必备元素**

断言：

1. 存在侧栏区 `data-testid="tour-workspace-sidebar"`
2. 存在标签区 `data-testid="tour-secondary-tabs"`
3. 当前标签内容区域存在

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSessionPanel.test.js`
Expected: FAIL

- [ ] **Step 3: 在 `TourWorkspace.vue` 落地双栏结构与基础状态绑定**

```vue
<section class="tour-workspace">
  <TourWorkspaceSidebar ... />
  <div class="tour-workspace-main">
    <TourSecondaryTabs ... />
    <div class="tour-workspace-panel">
      <!-- panel slots -->
    </div>
  </div>
</section>
```

- [ ] **Step 4: 确认测试通过并补充基本样式**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSessionPanel.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour/TourWorkspace.vue frontend/src/components/tour/workspace/TourSecondaryTabs.vue frontend/src/components/tour/workspace/TourWorkspaceSidebar.vue frontend/src/components/tour/workspace/__tests__/TourSessionPanel.test.js
git commit -m "feat(frontend): scaffold tour workspace layout and secondary tabs"
```

---

## Chunk 3: Four Tab Panels and Feature Behavior

### Task 5: 实现 `导览会话` 面板（流式消息 + 输入 + 快捷提问）

**Files:**
- Create: `frontend/src/components/tour/workspace/TourSessionPanel.vue`
- Modify: `frontend/src/components/tour/TourWorkspace.vue`
- Test: `frontend/src/components/tour/workspace/__tests__/TourSessionPanel.test.js`

- [ ] **Step 1: 写失败测试（发送按钮可用、流式内容可见、草稿不丢）**

核心断言：

1. 输入框与发送按钮渲染
2. `streamingContent` 存在时展示流式气泡
3. 切换标签后再切回，草稿仍在

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSessionPanel.test.js`
Expected: FAIL

- [ ] **Step 3: 实现会话面板并接入 `useTour + useTourWorkbench`**

关键点：

1. 输入绑定 `chatDraft`
2. 发送时调用 `buildStyledPrompt` 生成发送文本
3. UI 上仍显示用户原始输入
4. 快捷提问 chips 点击只改草稿

- [ ] **Step 4: 测试回归**

Run:
- `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSessionPanel.test.js`
- `cd frontend && npm run test -- --run src/composables/__tests__/useTour.test.js`

Expected: PASS（无导览会话回归）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour/workspace/TourSessionPanel.vue frontend/src/components/tour/workspace/__tests__/TourSessionPanel.test.js frontend/src/components/tour/TourWorkspace.vue
git commit -m "feat(frontend): add tour session panel with streamed chat and prompt controls"
```

---

### Task 6: 实现 `展品速览` 面板（模板菜单补全）

**Files:**
- Create: `frontend/src/components/tour/workspace/TourExhibitQuickView.vue`
- Modify: `frontend/src/components/tour/TourWorkspace.vue`
- Modify: `frontend/src/composables/useTourWorkbench.js`
- Test: `frontend/src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js`

- [ ] **Step 1: 写失败测试（点击模板后填充草稿并切换标签）**

```js
it('fills draft with selected exhibit template and switches to session tab', async () => {
  // mount quick view with exhibits
  // select template item
  // expect activeTab === 'session'
  // expect chatDraft.value to match template text
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js`
Expected: FAIL

- [ ] **Step 3: 实现模板菜单与回填逻辑**

模板 key 约定：

- `intro` -> `介绍一下{{name}}`
- `controversy` -> `{{name}}有什么历史争议？`
- `relation` -> `{{name}}和其他展品有什么联系？`

回调流程：

1. 调 `insertTemplateForExhibit`
2. emit `switch-tab('session')`
3. 聚焦输入框（由 `TourWorkspace` 触发）

- [ ] **Step 4: 运行测试验证**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour/workspace/TourExhibitQuickView.vue frontend/src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js frontend/src/composables/useTourWorkbench.js frontend/src/components/tour/TourWorkspace.vue
git commit -m "feat(frontend): add exhibit quick view with template menu and draft autofill"
```

---

### Task 7: 实现 `导览进度` 面板（进度可视 + 行动按钮）

**Files:**
- Create: `frontend/src/components/tour/workspace/TourProgressPanel.vue`
- Modify: `frontend/src/components/tour/TourWorkspace.vue`
- Test: `frontend/src/components/tour/workspace/__tests__/TourSessionPanel.test.js`（或新增 `TourProgressPanel.test.js`）

- [ ] **Step 1: 写失败测试（展示进度并触发行动事件）**

断言：

1. 展示 `currentHall`、`exhibitIndex`、总展品数
2. 点击“下一个展品” emit 对应事件
3. 点击“完成本展厅”触发 `completeHall`

- [ ] **Step 2: 运行失败测试**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourProgressPanel.test.js`
Expected: FAIL

- [ ] **Step 3: 实现面板与行为透传**

1. 只做 UI 聚合，不改业务逻辑
2. 事件向上抛给 `TourWorkspace`
3. `TourWorkspace` 内调用已有 `useTour` 方法

- [ ] **Step 4: 回归测试**

Run:
- `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourProgressPanel.test.js`
- `cd frontend && npm run test -- --run src/composables/__tests__/useTour.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour/workspace/TourProgressPanel.vue frontend/src/components/tour/workspace/__tests__/TourProgressPanel.test.js frontend/src/components/tour/TourWorkspace.vue
git commit -m "feat(frontend): add tour progress panel and action controls"
```

---

### Task 8: 实现 `导览设置` 面板（偏好 + 风格 + TTS占位）

**Files:**
- Create: `frontend/src/components/tour/workspace/TourSettingsPanel.vue`
- Modify: `frontend/src/composables/useTourWorkbench.js`
- Test: `frontend/src/components/tour/workspace/__tests__/TourSettingsPanel.test.js`

- [ ] **Step 1: 写失败测试（设置读写、重置、TTS占位可见）**

核心断言：

1. 回答长短/讲解深浅/术语难度控件渲染
2. 修改后 composable 状态更新
3. TTS 区域显示“即将上线”
4. 恢复默认按钮可回退

- [ ] **Step 2: 运行失败测试**

Run: `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSettingsPanel.test.js`
Expected: FAIL

- [ ] **Step 3: 最小实现设置面板与持久化**

1. 控件绑定 `uiPreferences/stylePreferences/ttsPreferences`
2. 设置改变立即持久化
3. TTS 控件禁用态+说明文案

- [ ] **Step 4: 测试回归**

Run:
- `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSettingsPanel.test.js`
- `cd frontend && npm run test -- --run src/composables/__tests__/useTourWorkbench.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour/workspace/TourSettingsPanel.vue frontend/src/components/tour/workspace/__tests__/TourSettingsPanel.test.js frontend/src/composables/useTourWorkbench.js

git commit -m "feat(frontend): add tour settings panel with style preferences and tts placeholders"
```

---

## Chunk 4: Responsive, Styling Harmonization, and Final Verification

### Task 9: 移动端适配（工具抽屉 + 标签可滚动 + 输入粘底）

**Files:**
- Modify: `frontend/src/components/tour/TourWorkspace.vue`
- Modify: `frontend/src/components/tour/workspace/TourWorkspaceSidebar.vue`
- Modify: `frontend/src/components/tour/workspace/TourSessionPanel.vue`
- Modify: `frontend/src/styles/custom.css`
- Test: `frontend/src/components/layout/__tests__/AppShellResponsive.test.js`

- [ ] **Step 1: 写失败测试（移动端工具区抽屉入口存在）**

测试目标：

1. 小屏时显示工具按钮
2. 点击后打开抽屉并渲染侧栏

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/layout/__tests__/AppShellResponsive.test.js`
Expected: FAIL（当前无 tour workspace 移动抽屉逻辑）

- [ ] **Step 3: 实现移动布局与样式策略**

要求：

1. `<768` 时左侧功能区改为 `AppDrawer`
2. 二级标签容器 `overflow-x: auto`
3. 输入区 `position: sticky; bottom: env(safe-area-inset-bottom)`
4. 禁止横向滚动

- [ ] **Step 4: 测试与手工验证**

Run:
- `cd frontend && npm run test -- --run src/components/layout/__tests__/AppShellResponsive.test.js`
- `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSessionPanel.test.js`

Manual:
- 浏览器 DevTools 切换 `390x844`
- 验证输入区不被键盘遮挡（模拟移动设备）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour/TourWorkspace.vue frontend/src/components/tour/workspace/TourWorkspaceSidebar.vue frontend/src/components/tour/workspace/TourSessionPanel.vue frontend/src/styles/custom.css frontend/src/components/layout/__tests__/AppShellResponsive.test.js
git commit -m "feat(frontend): complete mobile adaptations for tour workspace"
```

---

### Task 10: 视觉融合收尾（浅色主基调 + 局部沉浸）

**Files:**
- Modify: `frontend/src/components/tour/TourWorkspace.vue`
- Modify: `frontend/src/components/tour/workspace/TourSessionPanel.vue`
- Modify: `frontend/src/components/tour/workspace/TourSecondaryTabs.vue`
- Modify: `frontend/src/components/tour/workspace/TourExhibitQuickView.vue`
- Modify: `frontend/src/components/tour/workspace/TourProgressPanel.vue`
- Modify: `frontend/src/components/tour/workspace/TourSettingsPanel.vue`

- [ ] **Step 1: 写/更新样式快照测试（可选）**

若仓库无快照策略，至少补 DOM 类名断言：

1. 主容器使用浅色 token 类
2. 会话消息区使用局部深色类

- [ ] **Step 2: 应用 token 化视觉样式**

约束：

1. 不新增硬编码主题色
2. 不恢复整页深色壳层
3. 保留局部沉浸区

- [ ] **Step 3: 回归关键 UI 测试**

Run:
- `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js`
- `cd frontend && npm run test -- --run src/components/tour/workspace/__tests__/TourSettingsPanel.test.js`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/tour/workspace frontend/src/components/tour/TourWorkspace.vue
git commit -m "style(frontend): harmonize tour workspace with museum design system"
```

---

### Task 11: 全量回归与验收记录

**Files:**
- Modify: `docs/superpowers/plans/2026-04-29-tour-workspace-redesign.md`（勾选执行状态时）
- Optional Create: `docs/superpowers/plans/2026-04-29-tour-workspace-redesign-verification.md`

- [ ] **Step 1: 跑前端关键测试集**

Run:

```bash
cd frontend
npm run test -- --run src/composables/__tests__/useTourWorkbench.test.js
npm run test -- --run src/components/tour/workspace/__tests__/TourSessionPanel.test.js
npm run test -- --run src/components/tour/workspace/__tests__/TourExhibitQuickView.test.js
npm run test -- --run src/components/tour/workspace/__tests__/TourSettingsPanel.test.js
npm run test -- --run src/components/tour/__tests__/TourViewWorkspaceGate.test.js
npm run test -- --run src/composables/__tests__/useTour.test.js
```

Expected: all PASS

- [ ] **Step 2: 手工回归（1280 / 768 / 390）**

Checklist:

1. `/tour` 顶部导航可见
2. 仅 `tourStep='tour'` 有工作台
3. 四标签可切换
4. 模板菜单填充+切回会话生效
5. 风格设置能影响发送文本
6. TTS 占位显示明确
7. 手机端无横向滚动

- [ ] **Step 3: 产出验收记录（建议）**

在 `verification.md` 记录：

1. 测试命令
2. 截图说明
3. 已知限制

- [ ] **Step 4: 最终 Commit（若执行阶段产生文件）**

```bash
git add frontend docs/superpowers/plans/2026-04-29-tour-workspace-redesign-verification.md
git commit -m "test(frontend): verify tour workspace redesign across desktop and mobile"
```

---

## Risks and Mitigations

1. 风格注入影响答案质量
   - Mitigation: 提供总开关，可回退纯原始输入
2. 旧 `ExhibitTour` 逻辑拆分导致行为回归
   - Mitigation: 保留 `useTour` 调用路径不变，先写 gate 与行为测试
3. 移动端键盘遮挡输入
   - Mitigation: sticky + safe-area + 真机/DevTools 双验证
4. 过度样式改动再次破坏一致性
   - Mitigation: 强制 token 化，限制硬编码色

---

## Definition of Done

1. `/tour` 不再隐藏全站顶部导航
2. 仅 `tourStep='tour'` 展示工作台
3. 工作台含四标签与左侧混合功能区
4. 展品模板菜单可填充草稿并切回会话
5. 对话风格参数可通过前端注入生效
6. TTS 设置已占位且清晰标注未上线
7. 移动端可用性达标（无横向滚动、输入不遮挡）
8. 关键自动化测试全部通过

---

Plan complete and saved to `docs/superpowers/plans/2026-04-29-tour-workspace-redesign.md`. Ready to execute?
