# MuseAI 前端博物馆风重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改动后端协议与核心业务逻辑的前提下，完成 MuseAI 前端三阶段博物馆风重构，统一 design token、侧边栏信息架构、Tour 暗色视觉与移动端可用性。

**Architecture:** 采用分层 design-system（tokens/motifs/components/theme）作为唯一视觉源，前台与后台通过 Element Plus 语义变量映射自动继承风格。路由使用 `meta.sidebar` 驱动侧边栏类型，`App.vue` 统一处理桌面常驻与移动抽屉。Tour 页面仅迁移视觉层，不改状态机与交互流程。

**Tech Stack:** Vue 3 (`<script setup>`), Vue Router 4, Element Plus 2.13.6, Vite, Vitest

**Spec:** `docs/superpowers/specs/2026-04-21-frontend-museum-redesign-design.md`

---

## Scope and Phase Gates

- **Phase 1（设计系统骨架）**: 交付 design-system 目录、Element 主题映射、母题组件、封装组件、`/design-system` 预览页、站点元信息和 favicon。
- **Phase 2（信息架构与核心页面）**: 交付路由驱动侧边栏、抽屉、首页问答重构、展品/导览助手/个人设置迁移、登录对话框升级、404 和空状态替换、移动端适配。
- **Phase 3（Tour 与 Admin 收尾）**: 交付 Tour 暗色 token 迁移与装饰母题、Admin 轻量适配、全站回归与体积门禁。

---

## File Structure (Locked Before Implementation)

### Phase 1 - Create

- `frontend/src/design-system/tokens/colors.css`
- `frontend/src/design-system/tokens/typography.css`
- `frontend/src/design-system/tokens/spacing.css`
- `frontend/src/design-system/tokens/radii.css`
- `frontend/src/design-system/tokens/shadows.css`
- `frontend/src/design-system/tokens/motion.css`
- `frontend/src/design-system/tokens/breakpoints.css`
- `frontend/src/design-system/tokens/breakpoints.js`
- `frontend/src/design-system/tokens/index.css`
- `frontend/src/design-system/element-theme.css`
- `frontend/src/design-system/index.css`
- `frontend/src/design-system/motifs/symbols/FishFaceSymbol.vue`
- `frontend/src/design-system/motifs/symbols/FishSwim.vue`
- `frontend/src/design-system/motifs/patterns/RopePattern.vue`
- `frontend/src/design-system/motifs/patterns/NetPattern.vue`
- `frontend/src/design-system/motifs/patterns/TrianglePattern.vue`
- `frontend/src/design-system/motifs/artifacts/PointedJar.vue`
- `frontend/src/design-system/motifs/artifacts/FishFaceBasin.vue`
- `frontend/src/design-system/motifs/artifacts/ClayPot.vue`
- `frontend/src/design-system/motifs/index.js`
- `frontend/src/design-system/components/MuseumPage.vue`
- `frontend/src/design-system/components/MuseumCard.vue`
- `frontend/src/design-system/components/MuseumButton.vue`
- `frontend/src/design-system/components/MuseumDialog.vue`
- `frontend/src/design-system/components/MuseumInput.vue`
- `frontend/src/design-system/components/SectionDivider.vue`
- `frontend/src/design-system/components/EmptyState.vue`
- `frontend/src/design-system/components/AppDrawer.vue`
- `frontend/src/design-system/components/index.js`
- `frontend/src/design-system/components/__tests__/EmptyState.test.js`
- `frontend/src/design-system/tokens/__tests__/breakpoints.test.js`
- `frontend/src/views/DesignSystemView.vue`
- `frontend/src/router/__tests__/design-system-route.test.js`
- `frontend/public/favicon.svg`

### Phase 1 - Modify

- `frontend/src/main.js`
- `frontend/src/router/index.js`
- `frontend/index.html`
- `frontend/src/components/layout/AppHeader.vue`

### Phase 2 - Create

- `frontend/src/composables/useMediaQuery.js`
- `frontend/src/components/layout/sidebars/ChatSessionsSidebar.vue`
- `frontend/src/components/layout/sidebars/ExhibitFilterSidebar.vue`
- `frontend/src/components/layout/sidebars/TourPlanSidebar.vue`
- `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`
- `frontend/src/components/chat/ChatMainArea.vue`
- `frontend/src/views/NotFoundView.vue`
- `frontend/src/components/layout/__tests__/AppShellResponsive.test.js`
- `frontend/src/components/chat/__tests__/ChatMainArea.test.js`
- `frontend/src/router/__tests__/not-found-route.test.js`

### Phase 2 - Modify

- `frontend/src/App.vue`
- `frontend/src/router/index.js`
- `frontend/src/components/layout/AppSidebar.vue`
- `frontend/src/components/layout/AppHeader.vue`
- `frontend/src/views/HomeView.vue`
- `frontend/src/components/ChatPanel.vue` (重命名为 `ChatMainArea.vue` 后保留兼容导出或删除)
- `frontend/src/views/ExhibitsView.vue`
- `frontend/src/views/CuratorView.vue`
- `frontend/src/components/profile/ProfileSettings.vue`
- `frontend/src/components/auth/AuthModal.vue`
- `frontend/src/components/auth/LoginForm.vue`
- `frontend/src/components/auth/RegisterForm.vue`
- `frontend/src/components/exhibits/ExhibitList.vue`
- `frontend/src/components/layout/FloorMap.vue`
- `frontend/src/views/AdminView.vue`
- `frontend/src/components/layout/__tests__/AppSidebar.test.js`
- `frontend/src/components/profile/__tests__/ProfileSettings.test.js`
- `frontend/src/styles/custom.css`

### Phase 3 - Modify

- `frontend/src/App.vue`
- `frontend/src/views/TourView.vue`
- `frontend/src/components/tour/OnboardingQuiz.vue`
- `frontend/src/components/tour/OpeningNarrative.vue`
- `frontend/src/components/tour/HallSelect.vue`
- `frontend/src/components/tour/HallIntro.vue`
- `frontend/src/components/tour/ExhibitTour.vue`
- `frontend/src/components/tour/ExhibitChat.vue`
- `frontend/src/components/tour/ExhibitNavigator.vue`
- `frontend/src/components/tour/TourReport.vue`
- `frontend/src/components/tour/RadarChart.vue`
- `frontend/src/components/tour/IdentityTags.vue`
- `frontend/src/components/tour/TourOneLiner.vue`
- `frontend/src/components/tour/TourStats.vue`
- `frontend/src/components/admin/DocumentManager.vue`
- `frontend/src/components/admin/HallManager.vue`
- `frontend/src/components/admin/ExhibitManager.vue`
- `frontend/src/components/admin/TourPathManager.vue`
- `frontend/src/components/admin/PromptManager.vue`
- `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`
- `frontend/src/components/tour/__tests__/ExhibitTour.test.js`
- `frontend/src/components/layout/__tests__/AppSidebar.test.js`

---

## Phase 1: 设计系统骨架

### Task 1: 建立 Token 与主题入口

**Files:**
- Create: `frontend/src/design-system/tokens/__tests__/breakpoints.test.js`
- Create: `frontend/src/design-system/tokens/breakpoints.js`
- Create: `frontend/src/design-system/tokens/*.css`
- Create: `frontend/src/design-system/element-theme.css`
- Create: `frontend/src/design-system/index.css`
- Modify: `frontend/src/main.js`

- [ ] **Step 1: 先写失败测试，锁定断点常量 API**

```js
import { describe, it, expect } from 'vitest'
import { BREAKPOINTS } from '../breakpoints.js'

describe('design-system breakpoints', () => {
  it('exports the 5 required breakpoints', () => {
    expect(BREAKPOINTS).toEqual({
      xs: 0,
      sm: 640,
      md: 768,
      lg: 1024,
      xl: 1280,
    })
  })
})
```

- [ ] **Step 2: 运行测试并确认失败（模块尚不存在）**

Run: `cd frontend && npm run test -- --run src/design-system/tokens/__tests__/breakpoints.test.js`
Expected: FAIL with module resolution error for `breakpoints.js`

- [ ] **Step 3: 实现 breakpoints.js 与 token 聚合入口**

```js
// frontend/src/design-system/tokens/breakpoints.js
export const BREAKPOINTS = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
}
```

```css
/* frontend/src/design-system/tokens/index.css */
@import './colors.css';
@import './typography.css';
@import './spacing.css';
@import './radii.css';
@import './shadows.css';
@import './motion.css';
@import './breakpoints.css';
```

- [ ] **Step 4: 接入全局入口，确保 Element Plus 变量映射生效**

```css
/* frontend/src/design-system/index.css */
@import './tokens/index.css';
@import './element-theme.css';
```

```js
// frontend/src/main.js
import './design-system/index.css'
```

- [ ] **Step 5: 验证测试与构建**

Run: `cd frontend && npm run test -- --run src/design-system/tokens/__tests__/breakpoints.test.js`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: build success

- [ ] **Step 6: Commit**

```bash
git add frontend/src/design-system frontend/src/main.js
git commit -m "feat(frontend): add design-system tokens and theme entry"
```

### Task 2: 实现 SVG 母题与基础封装组件

**Files:**
- Create: `frontend/src/design-system/motifs/**/*.vue`
- Create: `frontend/src/design-system/motifs/index.js`
- Create: `frontend/src/design-system/components/*.vue`
- Create: `frontend/src/design-system/components/index.js`
- Create: `frontend/src/design-system/components/__tests__/EmptyState.test.js`

- [ ] **Step 1: 先写 EmptyState 失败测试，锁定 icon 映射契约**

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyState from '../EmptyState.vue'

describe('EmptyState', () => {
  it('renders jar motif when icon=jar', () => {
    const wrapper = mount(EmptyState, {
      props: { icon: 'jar', title: '空', description: '空状态' },
      global: { stubs: ['PointedJar', 'FishFaceBasin', 'FishSwim'] },
    })
    expect(wrapper.text()).toContain('空状态')
  })
})
```

- [ ] **Step 2: 运行测试并确认失败（组件不存在）**

Run: `cd frontend && npm run test -- --run src/design-system/components/__tests__/EmptyState.test.js`
Expected: FAIL with missing component error

- [ ] **Step 3: 实现母题组件统一 API（size/color/variant）**

```vue
<script setup>
const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: '半坡纹样' },
})

const pixelSize = typeof props.size === 'number' ? `${props.size}px` : props.size
</script>
```

- [ ] **Step 4: 实现组件封装层并导出 barrel**

```js
// frontend/src/design-system/components/index.js
export { default as MuseumPage } from './MuseumPage.vue'
export { default as MuseumCard } from './MuseumCard.vue'
export { default as MuseumButton } from './MuseumButton.vue'
export { default as MuseumDialog } from './MuseumDialog.vue'
export { default as MuseumInput } from './MuseumInput.vue'
export { default as SectionDivider } from './SectionDivider.vue'
export { default as EmptyState } from './EmptyState.vue'
export { default as AppDrawer } from './AppDrawer.vue'
```

- [ ] **Step 5: 运行组件测试**

Run: `cd frontend && npm run test -- --run src/design-system/components/__tests__/EmptyState.test.js`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/design-system
git commit -m "feat(frontend): add museum motifs and wrapped design components"
```

### Task 3: 建立预览路由并完成站点元信息改造

**Files:**
- Create: `frontend/src/views/DesignSystemView.vue`
- Create: `frontend/src/router/__tests__/design-system-route.test.js`
- Create: `frontend/public/favicon.svg`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/index.html`
- Modify: `frontend/src/components/layout/AppHeader.vue`

- [ ] **Step 1: 先写路由失败测试，锁定 `/design-system` 存在性**

```js
import { describe, it, expect } from 'vitest'
import router from '../index.js'

describe('design-system route', () => {
  it('contains /design-system route', () => {
    const target = router.getRoutes().find((r) => r.path === '/design-system')
    expect(target).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行测试并确认失败（路由未注册）**

Run: `cd frontend && npm run test -- --run src/router/__tests__/design-system-route.test.js`
Expected: FAIL with missing route assertion

- [ ] **Step 3: 实现预览页与路由注册**

```js
{
  path: '/design-system',
  name: 'design-system',
  component: () => import('../views/DesignSystemView.vue'),
  meta: { title: 'Design System', sidebar: null },
}
```

- [ ] **Step 4: 更新 index 元信息、favicon、Header 品牌**

```html
<meta name="theme-color" content="#a94c2c">
<meta name="description" content="沉浸式 AI 博物馆导览系统 —— 与半坡新石器时代展开对话">
<title>MuseAI · 半坡博物馆智能导览</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
```

- [ ] **Step 5: 验证路由测试与构建**

Run: `cd frontend && npm run test -- --run src/router/__tests__/design-system-route.test.js`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: build success

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/DesignSystemView.vue frontend/src/router/index.js frontend/src/router/__tests__/design-system-route.test.js frontend/index.html frontend/public/favicon.svg frontend/src/components/layout/AppHeader.vue
git commit -m "feat(frontend): add design-system preview route and museum metadata"
```

### Task 4: Phase 1 验收门禁

**Files:**
- Verify only (no new code)

- [ ] **Step 1: 运行阶段回归测试集**

Run: `cd frontend && npm run test -- --run src/design-system/tokens/__tests__/breakpoints.test.js src/design-system/components/__tests__/EmptyState.test.js src/router/__tests__/design-system-route.test.js`
Expected: all PASS

- [ ] **Step 2: 运行 lint 与构建**

Run: `cd frontend && npm run lint && npm run build`
Expected: no lint errors, build success

- [ ] **Step 3: 手动验收**

Run: `cd frontend && npm run dev`
Expected:
- `/design-system` 可访问，色板/字体/间距/母题/组件可视
- 全站 Element Plus 主色已迁移到赭红
- 浏览器标签与 favicon 已更新

- [ ] **Step 4: Commit 阶段标记**

```bash
git add -A
git commit -m "chore(frontend): complete phase 1 museum design system baseline"
```

---

## Phase 2: 侧边栏重构与核心前台页面

### Task 5: 路由驱动侧边栏与移动抽屉框架

**Files:**
- Create: `frontend/src/composables/useMediaQuery.js`
- Create: `frontend/src/components/layout/sidebars/ChatSessionsSidebar.vue`
- Create: `frontend/src/components/layout/sidebars/ExhibitFilterSidebar.vue`
- Create: `frontend/src/components/layout/sidebars/TourPlanSidebar.vue`
- Create: `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`
- Create: `frontend/src/components/layout/__tests__/AppShellResponsive.test.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/components/layout/AppHeader.vue`
- Modify: `frontend/src/components/layout/__tests__/AppSidebar.test.js`

- [ ] **Step 1: 先写失败测试，锁定 sidebar type 渲染和移动抽屉触发**

```js
it('renders chat sidebar when type=chat-sessions', async () => {
  const wrapper = mount(AppSidebar, {
    props: { type: 'chat-sessions' },
    global: { stubs: ['ChatSessionsSidebar', 'ExhibitFilterSidebar', 'TourPlanSidebar', 'AdminNavSidebar'] },
  })
  expect(wrapper.html()).toContain('chat-sessions')
})
```

- [ ] **Step 2: 运行测试并确认失败（新 API 尚未实现）**

Run: `cd frontend && npm run test -- --run src/components/layout/__tests__/AppSidebar.test.js src/components/layout/__tests__/AppShellResponsive.test.js`
Expected: FAIL with prop mismatch / missing drawer behavior

- [ ] **Step 3: 实现 `meta.sidebar`、`useMediaQuery`、`App.vue` 双模式布局**

```js
// frontend/src/composables/useMediaQuery.js
import { ref, onMounted, onUnmounted } from 'vue'

export function useMediaQuery(query) {
  const matches = ref(false)
  let media

  const sync = () => { matches.value = !!media?.matches }

  onMounted(() => {
    media = window.matchMedia(query)
    sync()
    media.addEventListener('change', sync)
  })

  onUnmounted(() => {
    media?.removeEventListener('change', sync)
  })

  return matches
}
```

- [ ] **Step 4: 重写 AppSidebar 为薄壳，挂接四类侧边栏子组件**

```vue
<template>
  <aside class="app-sidebar">
    <ChatSessionsSidebar v-if="type === 'chat-sessions'" />
    <ExhibitFilterSidebar v-else-if="type === 'exhibit-filters'" />
    <TourPlanSidebar v-else-if="type === 'tour-plan'" />
    <AdminNavSidebar v-else-if="type === 'admin-nav'" />
  </aside>
</template>
```

- [ ] **Step 5: 运行测试**

Run: `cd frontend && npm run test -- --run src/components/layout/__tests__/AppSidebar.test.js src/components/layout/__tests__/AppShellResponsive.test.js`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.vue frontend/src/router/index.js frontend/src/composables/useMediaQuery.js frontend/src/components/layout/AppSidebar.vue frontend/src/components/layout/AppHeader.vue frontend/src/components/layout/sidebars frontend/src/components/layout/__tests__
git commit -m "feat(frontend): add route-driven sidebars and responsive app shell"
```

### Task 6: 首页问答重构（会话列表外移）

**Files:**
- Create: `frontend/src/components/chat/ChatMainArea.vue`
- Create: `frontend/src/components/chat/__tests__/ChatMainArea.test.js`
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/components/layout/sidebars/ChatSessionsSidebar.vue`
- Modify: `frontend/src/composables/useChat.js`
- Modify/Delete: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: 先写失败测试，锁定 ChatMainArea 不再渲染内嵌会话栏**

```js
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import ChatMainArea from '../ChatMainArea.vue'

describe('ChatMainArea', () => {
  it('does not render embedded session list', () => {
    const wrapper = mount(ChatMainArea, { global: { stubs: ['MessageItem', 'SourceCard'] } })
    expect(wrapper.find('.chat-session-pane').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试并确认失败（组件尚未实现）**

Run: `cd frontend && npm run test -- --run src/components/chat/__tests__/ChatMainArea.test.js`
Expected: FAIL

- [ ] **Step 3: 实现 `ChatMainArea.vue`，将会话管理职责迁移到 `ChatSessionsSidebar.vue`**

```vue
<!-- 关键结构：仅保留消息流、RAG思考、输入区 -->
<div class="chat-main-area">
  <div class="chat-messages">...</div>
  <div class="chat-input">...</div>
</div>
```

- [ ] **Step 4: 更新 `HomeView.vue` 使用 `MuseumPage + hero + ChatMainArea`**

```vue
<MuseumPage>
  <template #hero>
    <h1>与半坡对话</h1>
    <p>六千年的陶土之下，每一个疑问都值得追问</p>
  </template>
  <ChatMainArea />
</MuseumPage>
```

- [ ] **Step 5: 运行测试**

Run: `cd frontend && npm run test -- --run src/components/chat/__tests__/ChatMainArea.test.js src/components/layout/__tests__/AppSidebar.test.js`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/chat frontend/src/views/HomeView.vue frontend/src/components/layout/sidebars/ChatSessionsSidebar.vue frontend/src/composables/useChat.js frontend/src/components/ChatPanel.vue
git commit -m "feat(frontend): refactor home chat area and externalize sessions sidebar"
```

### Task 7: 展品页/导览助手/个人设置迁移

**Files:**
- Modify: `frontend/src/views/ExhibitsView.vue`
- Modify: `frontend/src/components/exhibits/ExhibitList.vue`
- Modify: `frontend/src/components/layout/FloorMap.vue`
- Modify: `frontend/src/views/CuratorView.vue`
- Modify: `frontend/src/components/layout/sidebars/ExhibitFilterSidebar.vue`
- Modify: `frontend/src/components/layout/sidebars/TourPlanSidebar.vue`
- Modify: `frontend/src/components/profile/ProfileSettings.vue`
- Modify: `frontend/src/components/profile/__tests__/ProfileSettings.test.js`

- [ ] **Step 1: 先写失败测试，锁定个人设置页面新的卡片分段结构仍可保存**

```js
it('still calls api.profile.update after redesign', async () => {
  const wrapper = mount(ProfileSettings, { global: { stubs: { 'el-card': true, 'el-form': true, 'el-form-item': true, 'el-button': true } } })
  await wrapper.vm.$nextTick()
  await wrapper.find('button').trigger('click')
  expect(api.profile.update).toHaveBeenCalled()
})
```

- [ ] **Step 2: 运行测试并确认失败（结构调整后需修复选择器）**

Run: `cd frontend && npm run test -- --run src/components/profile/__tests__/ProfileSettings.test.js`
Expected: FAIL

- [ ] **Step 3: 完成三页布局改造与响应式断点**

```css
@media (max-width: 767px) {
  .exhibits-grid {
    grid-template-columns: 1fr;
  }

  .curator-main {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: 替换展品卡片为 MuseumCard，并将图片统一为 16:9**

```css
.exhibit-image {
  aspect-ratio: 16 / 9;
  width: 100%;
  object-fit: cover;
}
```

- [ ] **Step 5: 运行测试与构建**

Run: `cd frontend && npm run test -- --run src/components/profile/__tests__/ProfileSettings.test.js src/components/layout/__tests__/AppSidebar.test.js`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: build success

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ExhibitsView.vue frontend/src/components/exhibits/ExhibitList.vue frontend/src/components/layout/FloorMap.vue frontend/src/views/CuratorView.vue frontend/src/components/layout/sidebars/ExhibitFilterSidebar.vue frontend/src/components/layout/sidebars/TourPlanSidebar.vue frontend/src/components/profile/ProfileSettings.vue frontend/src/components/profile/__tests__/ProfileSettings.test.js
git commit -m "feat(frontend): migrate exhibits curator and profile to museum design system"
```

### Task 8: 登录对话框、空状态替换、404 路由

**Files:**
- Create: `frontend/src/views/NotFoundView.vue`
- Create: `frontend/src/router/__tests__/not-found-route.test.js`
- Modify: `frontend/src/components/auth/AuthModal.vue`
- Modify: `frontend/src/components/auth/LoginForm.vue`
- Modify: `frontend/src/components/auth/RegisterForm.vue`
- Modify: `frontend/src/views/CuratorView.vue`
- Modify: `frontend/src/components/exhibits/ExhibitList.vue`
- Modify: `frontend/src/components/admin/TourPathManager.vue`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 先写失败测试，锁定 catch-all 404 路由存在**

```js
import { describe, it, expect } from 'vitest'
import router from '../index.js'

describe('not found route', () => {
  it('contains catch-all path', () => {
    const hit = router.getRoutes().find((r) => r.path === '/:pathMatch(.*)*')
    expect(hit).toBeTruthy()
  })
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm run test -- --run src/router/__tests__/not-found-route.test.js`
Expected: FAIL

- [ ] **Step 3: 使用 MuseumDialog 重写 AuthModal，并实现移动端 fullscreen**

```vue
<MuseumDialog
  v-model:visible="visible"
  :title="mode === 'login' ? '欢迎回到半坡' : '创建你的导览身份'"
  mobile-fullscreen
>
  ...
</MuseumDialog>
```

- [ ] **Step 4: 新增 `NotFoundView.vue` 并注册 catch-all 路由；全站替换 `el-empty` 为 `EmptyState`**

Run: `cd frontend && rg "el-empty" src -g '*.vue'`
Expected: no matches

- [ ] **Step 5: 运行测试与构建**

Run: `cd frontend && npm run test -- --run src/router/__tests__/not-found-route.test.js src/components/layout/__tests__/AppSidebar.test.js`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: build success

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/auth frontend/src/views/NotFoundView.vue frontend/src/router/index.js frontend/src/router/__tests__/not-found-route.test.js frontend/src/views/CuratorView.vue frontend/src/components/exhibits/ExhibitList.vue frontend/src/components/admin/TourPathManager.vue
git commit -m "feat(frontend): redesign auth modal and add not-found plus unified empty state"
```

### Phase 2 Exit Criteria

- `/` `/exhibits` `/curator` `/profile` 均通过 token 样式渲染
- `<768` 时 sidebar 仅通过抽屉出现
- 登录弹窗移动端全屏
- 不存在业务页面 `el-empty` 旧组件残留

---

## Phase 3: Tour 暗版迁移与 Admin 适配

### Task 9: 全局主题切换与 Tour 外壳改造

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/views/TourView.vue`
- Create: `frontend/src/views/__tests__/app-theme-switch.test.js`

- [ ] **Step 1: 先写失败测试，锁定 `/tour` 时 html 上的 `data-theme=tour-dark`**

```js
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../../App.vue'

it('sets html data-theme to tour-dark on /tour', async () => {
  const router = createRouter({
    history: createWebHistory(),
    routes: [{ path: '/tour', component: { template: '<div />' } }],
  })
  router.push('/tour')
  await router.isReady()
  mount(App, { global: { plugins: [router], stubs: ['AppHeader', 'AppSidebar', 'AuthModal'] } })
  expect(document.documentElement.getAttribute('data-theme')).toBe('tour-dark')
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm run test -- --run src/views/__tests__/app-theme-switch.test.js`
Expected: FAIL

- [ ] **Step 3: 在 `App.vue` 增加 route watcher，统一设置/清理 html 主题属性**

```js
watch(
  () => route.path,
  (path) => {
    const theme = path.startsWith('/tour') ? 'tour-dark' : 'default'
    document.documentElement.setAttribute('data-theme', theme)
  },
  { immediate: true },
)
```

- [ ] **Step 4: 移除 `body.tour-mode` 样式耦合，改为 token 化容器样式**

Run: `cd frontend && npm run test -- --run src/views/__tests__/app-theme-switch.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.vue frontend/src/views/TourView.vue frontend/src/views/__tests__/app-theme-switch.test.js
git commit -m "feat(frontend): add route-driven tour dark theme switch"
```

### Task 10: Tour 子组件视觉迁移（交互不变）

**Files:**
- Modify: `frontend/src/components/tour/OnboardingQuiz.vue`
- Modify: `frontend/src/components/tour/OpeningNarrative.vue`
- Modify: `frontend/src/components/tour/HallSelect.vue`
- Modify: `frontend/src/components/tour/HallIntro.vue`
- Modify: `frontend/src/components/tour/ExhibitTour.vue`
- Modify: `frontend/src/components/tour/ExhibitChat.vue`
- Modify: `frontend/src/components/tour/ExhibitNavigator.vue`
- Modify: `frontend/src/components/tour/TourReport.vue`
- Modify: `frontend/src/components/tour/RadarChart.vue`
- Modify: `frontend/src/components/tour/IdentityTags.vue`
- Modify: `frontend/src/components/tour/TourOneLiner.vue`
- Modify: `frontend/src/components/tour/TourStats.vue`
- Modify: `frontend/src/components/tour/__tests__/ExhibitTour.test.js`

- [ ] **Step 1: 先固定行为测试基线，防止视觉迁移破坏流程**

Run: `cd frontend && npm run test -- --run src/components/tour/__tests__/ExhibitTour.test.js`
Expected: PASS（迁移前基线）

- [ ] **Step 2: 完成 token 替换与母题注入（Onboarding/HallSelect/TourReport）**

```vue
<FishFaceSymbol :size="72" class="onboarding-mark" aria-label="半坡人面鱼纹" />
<SectionDivider :ornament="true" />
```

```css
.tour-container {
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  min-height: 100dvh;
}
```

- [ ] **Step 3: 移动端适配（单列、输入粘底、字号降级）**

```css
@media (max-width: 767px) {
  .hall-cards {
    grid-template-columns: 1fr;
  }

  .exhibit-chat-input {
    position: sticky;
    bottom: 0;
  }
}
```

- [ ] **Step 4: 回归 Tour 测试**

Run: `cd frontend && npm run test -- --run src/components/tour/__tests__/ExhibitTour.test.js`
Expected: PASS（交互未回归）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tour
git commit -m "feat(frontend): migrate tour visuals to museum dark token system"
```

### Task 11: Admin 轻量主题适配与后台侧边栏

**Files:**
- Modify: `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`
- Modify: `frontend/src/components/admin/DocumentManager.vue`
- Modify: `frontend/src/components/admin/HallManager.vue`
- Modify: `frontend/src/components/admin/ExhibitManager.vue`
- Modify: `frontend/src/components/admin/TourPathManager.vue`
- Modify: `frontend/src/components/admin/PromptManager.vue`
- Modify: `frontend/src/components/layout/__tests__/AppSidebar.test.js`

- [ ] **Step 1: 先写失败测试，锁定 admin 菜单项完整性**

```js
it('renders 5 admin nav items', async () => {
  await router.push('/admin')
  await router.isReady()
  const items = wrapper.findAll('.el-menu-item')
  expect(items.length).toBe(5)
})
```

- [ ] **Step 2: 运行测试并确认失败（组件迁移后选择器变化）**

Run: `cd frontend && npm run test -- --run src/components/layout/__tests__/AppSidebar.test.js`
Expected: FAIL

- [ ] **Step 3: 实现 AdminNavSidebar 激活态视觉与表格/表单 token 适配**

```css
.admin-nav .is-active {
  border-left: 3px solid var(--color-accent);
  background: var(--color-bg-subtle);
}

.admin-table :deep(.el-table__header th) {
  font-family: var(--font-family-serif);
  background: var(--color-bg-subtle);
}
```

- [ ] **Step 4: 运行测试**

Run: `cd frontend && npm run test -- --run src/components/layout/__tests__/AppSidebar.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/sidebars/AdminNavSidebar.vue frontend/src/components/admin frontend/src/components/layout/__tests__/AppSidebar.test.js
git commit -m "feat(frontend): align admin pages with museum tokens and sidebar style"
```

### Task 12: 全量验证、体积门禁与交付记录

**Files:**
- Modify (if needed): `docs/superpowers/specs/2026-04-21-frontend-museum-redesign-design.md`（仅回填实际差异）

- [ ] **Step 1: 运行前端全量测试**

Run: `cd frontend && npm run test -- --run`
Expected: PASS

- [ ] **Step 2: 运行 lint 与构建**

Run: `cd frontend && npm run lint && npm run build`
Expected: no lint errors, build success

- [ ] **Step 3: 验证 bundle 增量 <= 300KB（相对改造前基线）**

Run: `cd frontend && find dist/assets -type f -name '*.css' -o -name '*.js' | xargs -I{} stat -c '%n %s' {}`
Expected: 记录总量并与 Phase 0 基线对比，增量不超过 300KB（字体除外按规范单独记账）

- [ ] **Step 4: 执行手动回归矩阵（1280 / 768 / 375）**

必测路径：`/`, `/exhibits`, `/curator`, `/profile`, `/tour`, `/admin/exhibits`, `/admin/halls`, `/admin/documents`, `/admin/tour-paths`, `/admin/prompts`, `/design-system`, `/:pathMatch(.*)*`

- [ ] **Step 5: Commit 最终阶段**

```bash
git add -A
git commit -m "chore(frontend): complete phase 3 tour admin polish and verification"
```

---

## Execution Order and Parallelism

1. Phase 1 必须先完成（后续所有页面依赖 tokens 与封装组件）。
2. Phase 2 可以分两条并行流：
   - 流 A: App shell + sidebars + router
   - 流 B: Home/Exhibits/Curator/Profile + Auth/404
   最终在 Task 8 合流做回归。
3. Phase 3 先做 Task 9（主题切换），再做 Task 10（Tour），最后 Task 11（Admin）和 Task 12（总验收）。

---

## Risk Controls

- **字体体积风险:** 优先只打包 400 字重，600 在 Phase 3 后再决定是否保留。
- **测试脆弱性风险:** 组件测试中减少对内联样式字符串断言，改为结构和行为断言。
- **Element 版本风险:** 仅覆盖已验证的 CSS 变量，不覆盖内部 class 名。
- **回归风险:** 每个任务都带最小可运行测试；Phase Gate 强制 `test + lint + build`。
