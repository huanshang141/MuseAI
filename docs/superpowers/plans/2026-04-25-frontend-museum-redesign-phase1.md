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

