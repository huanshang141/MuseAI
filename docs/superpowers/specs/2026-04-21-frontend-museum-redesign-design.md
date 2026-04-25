# MuseAI 前端博物馆风重构 · 设计文档

**日期**:2026-04-21
**范围**:前端(`frontend/`)全量视觉与侧边栏重构
**交付节奏**:三阶段 PR

---

## 1. 背景与目标

### 1.1 当前痛点

- **侧边栏无价值**:`AppSidebar.vue` 四种模式中,`home` / `curator` / `exhibits` 三种仅展示静态占位文案或与主内容重复的 CTA,挤占 280px 屏幕空间
- **`/tour` 与其它页视觉脱节**:Tour 使用深蓝 `#1a1a2e` + 琥珀 `#d4a574` 的自定沉浸风,其它页用 Element Plus 默认浅蓝,两套审美无共通 design token
- **缺少博物馆气质**:正文宋体缺失、无 SVG 装饰母题、`index.html` 标题仍写着 "MuseAI API 测试面板"、默认 Element Plus el-empty 的灰色插图与项目定位脱节
- **无响应式适配**:所有页面按 `>=1280px` 桌面宽度设计,在移动端无法使用

### 1.2 目标

按项目愿景"去中心化的公共史学场域"与"沉浸式观展体验",建立**半坡陶土风**(terracotta-themed)的工业生产级 design system,覆盖:

1. 新建 `frontend/src/design-system/` 分层设计系统(tokens / motifs / components / theme)
2. 重构侧边栏:每种模式都承载真实功能,不再是占位
3. Tour 页配色迁移至新系统深色变体 + 加入 SVG 装饰层,**交互不动**
4. 其它页(问答/展品/导览助手/个人设置/管理后台)应用新 tokens + 封装组件
5. 全面 mobile 适配 (<768px)
6. 细节:登录对话框重设计 / `index.html` 元信息 / 空状态 & 404 / design-system 预览页

### 1.3 非目标

- 不换 Element Plus 为其它 UI 框架
- 不引入 Pinia/Vuex(保持现有 composable 架构)
- 不修改 API 协议或后端
- 不做国际化 i18n(保留中文)
- 不做全站暗色模式切换(暗色仅 Tour 页)
- 不做 SSR
- 不重构业务逻辑(composables 保留原样)

---

## 2. 设计决策(锁定项)

| 维度 | 决定 |
|---|---|
| **色板基调** | 半坡陶土 —— 赭红 / 素麻白 / 陶青 / 陶墨 + 铜金细线 |
| **构图与排版** | 现代博物馆(硬朗衬线、细金线分隔、几何构图、黄金比例) |
| **字体** | Source Han Serif(思源宋体),CSS 变量封装便于未来替换为商业字体 |
| **SVG 母题** | 综合系三层:符号(人面鱼纹/鱼纹)+ 纹样(绳纹/网纹/三角纹 pattern)+ 器物(尖底瓶/盆/罐轮廓) |
| **侧边栏策略** | 保留,按路由 meta 决定内容:会话列表 / 筛选器 / 路线规划 / 后台子导航 / null |
| **Tour 改造深度** | 交互不动,仅换配色 + 加 SVG 装饰 |
| **Admin 改造深度** | 轻量适配:应用 tokens 与字体,保留 el-table / el-form 结构 |
| **响应式** | 全面 mobile 适配,断点 640 / 768 / 1024 / 1280 |
| **架构方式** | 分层设计系统(方案 2):tokens / motifs / components 分目录解耦 |

---

## 3. 设计系统架构

### 3.1 目录结构

```
frontend/src/
├── design-system/
│   ├── tokens/
│   │   ├── colors.css            ← 色板变量(light + dark 两套)
│   │   ├── typography.css        ← 字号 / 行高 / 字族变量
│   │   ├── spacing.css           ← 4px 栅格间距
│   │   ├── radii.css             ← 圆角
│   │   ├── shadows.css           ← 阴影
│   │   ├── motion.css            ← 缓动 / 持续时间
│   │   ├── breakpoints.css       ← 断点常量 + media mixins
│   │   └── index.css             ← @import 聚合导出
│   ├── fonts/
│   │   └── source-han-serif/     ← WOFF2 自托管子集化字体
│   ├── motifs/                   ← SVG 作为 Vue SFC,支持 color prop
│   │   ├── symbols/
│   │   │   ├── FishFaceSymbol.vue
│   │   │   └── FishSwim.vue
│   │   ├── patterns/
│   │   │   ├── RopePattern.vue
│   │   │   ├── NetPattern.vue
│   │   │   └── TrianglePattern.vue
│   │   ├── artifacts/
│   │   │   ├── PointedJar.vue
│   │   │   ├── FishFaceBasin.vue
│   │   │   └── ClayPot.vue
│   │   └── index.js              ← 统一导出
│   ├── components/               ← 基于 Element Plus 再封装
│   │   ├── MuseumPage.vue        ← 统一页面骨架(breadcrumb + hero + content)
│   │   ├── MuseumCard.vue
│   │   ├── MuseumButton.vue
│   │   ├── MuseumDialog.vue
│   │   ├── MuseumInput.vue
│   │   ├── SectionDivider.vue    ← 铜金细线 + 可选中心符号
│   │   ├── EmptyState.vue        ← props icon='jar'|'basin'|'fish'
│   │   ├── AppDrawer.vue         ← 移动端侧边栏抽屉
│   │   └── index.js
│   ├── element-theme.css         ← 覆盖 --el-color-primary 等 Element Plus 变量
│   └── index.css                 ← 总入口(被 main.js 导入)
├── views/                        ← 现有 views 改用 design-system
├── components/
│   ├── layout/
│   │   ├── AppHeader.vue         ← 风格化(serif 字,金线 underline)
│   │   └── sidebars/             ← 拆出侧边栏子组件
│   │       ├── ChatSessionsSidebar.vue
│   │       ├── ExhibitFilterSidebar.vue
│   │       ├── TourPlanSidebar.vue
│   │       └── AdminNavSidebar.vue
│   └── ... (其它业务组件保留)
└── main.js                        ← 新增 `import '@/design-system'`
```

**命名规则**:所有 design-system 导出通过 `@/design-system` barrel 导入。各 view 禁止从 `frontend/src/components/` 直接导入 `MuseumCard` 这类组件。

### 3.2 设计令牌 tokens

#### 3.2.1 Colors (light 变体 - 前台非 Tour 页 + Admin)

```css
:root {
  /* —— 背景层 —— */
  --color-bg-base: #f5eedc;          /* 素麻白 - 全局背景 */
  --color-bg-elevated: #fdfaf2;      /* 纸白 - 卡片 */
  --color-bg-subtle: #efe5cc;        /* 浅陶 - 侧边栏 */
  --color-surface-card: #fbf5e6;     /* 卡片内层 */

  /* —— 文字层 —— */
  --color-text-primary: #2a2420;     /* 陶墨 - 主文 */
  --color-text-secondary: #5a5248;   /* 灰墨 - 副文 */
  --color-text-muted: #8a8074;       /* 浅墨 - 注释 */
  --color-text-inverse: #f5eedc;     /* 反色文字 */

  /* —— 主色 —— */
  --color-accent: #a94c2c;           /* 赭红 - primary */
  --color-accent-hover: #8f3f23;
  --color-accent-soft: #c47a52;      /* 柔赭 */
  --color-accent-muted: #e8d5a8;     /* 浅陶 */

  /* —— 辅色 —— */
  --color-jade: #5a7a6b;             /* 陶青 - success */
  --color-jade-soft: #7a9588;
  --color-gold-line: #c89d5a;        /* 铜金 - 装饰细线、warning */
  --color-danger: #8b2f1f;           /* 深赭 - danger,与 accent 区分 */

  /* —— 边界与分隔 —— */
  --color-border: #d9c9a8;
  --color-border-strong: #a89876;
  --color-divider: #c89d5a;

  /* —— 语义映射(给 Element Plus) —— */
  --color-primary: var(--color-accent);
  --color-success: var(--color-jade);
  --color-warning: var(--color-gold-line);
  --color-info: var(--color-text-muted);
}
```

#### 3.2.2 Colors (dark 变体 - 仅 Tour 页)

```css
:root[data-theme="tour-dark"] {
  --color-bg-base: #2a1f18;          /* 深炭 */
  --color-bg-elevated: #3a2b22;
  --color-bg-subtle: #1f1712;
  --color-surface-card: rgba(232, 213, 168, 0.05);

  --color-text-primary: #f0e6d3;     /* 奶白,沿用原 Tour */
  --color-text-secondary: rgba(240, 230, 211, 0.7);
  --color-text-muted: rgba(240, 230, 211, 0.45);

  --color-accent: #c47a52;           /* 深色上柔赭比赭红更易读 */
  --color-accent-soft: #d4a574;      /* 沿用原 Tour 琥珀 */
  --color-accent-muted: rgba(212, 165, 116, 0.2);

  --color-jade: #8fbc8f;             /* 沿用原 Tour */
  --color-gold-line: #c89d5a;

  --color-border: rgba(232, 213, 168, 0.15);
  --color-divider: rgba(200, 157, 90, 0.4);
}
```

Tour 页在 `App.vue` 检测到 `route.path.startsWith('/tour')` 时,给 `<html>` 加 `data-theme="tour-dark"` 属性。

#### 3.2.3 Typography

```css
:root {
  /* —— 字族 —— */
  --font-family-serif: 'Source Han Serif CN', 'Noto Serif CJK SC', 'SimSun', serif;
  --font-family-sans: 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-family-display: var(--font-family-serif);  /* 标题 / hero */
  --font-family-body: var(--font-family-serif);     /* 正文也用宋体 */
  --font-family-mono: 'JetBrains Mono', 'Fira Code', monospace;

  /* —— 字号 —— */
  --font-size-display: 48px;
  --font-size-h1: 32px;
  --font-size-h2: 24px;
  --font-size-h3: 20px;
  --font-size-h4: 18px;
  --font-size-body: 15px;
  --font-size-body-sm: 13px;
  --font-size-caption: 12px;
  --font-size-label: 11px;           /* uppercase + 字距 */

  /* —— 行高 —— */
  --line-height-tight: 1.3;
  --line-height-normal: 1.6;
  --line-height-relaxed: 2.0;        /* Tour 叙事段 */

  /* —— 字重 —— */
  --font-weight-regular: 400;
  --font-weight-semibold: 600;
  /* 不使用 Bold — 宋体 Bold 会 crush 细节 */
}
```

**字体加载策略**:
- Source Han Serif CN(Regular 400 + SemiBold 600)从 `design-system/fonts/source-han-serif/` 自托管,WOFF2 子集化至常用 7000 汉字,单字重 ~800KB
- `font-display: swap` 保证 FOUT 而非 FOIT
- 商业字体替换:只需改 `--font-family-serif` 变量值

#### 3.2.4 Spacing(4px 栅格)

```css
:root {
  --space-0: 0;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
}
```

#### 3.2.5 Radii(现代博物馆偏硬边,慎用大圆角)

```css
:root {
  --radius-none: 0;
  --radius-xs: 2px;        /* 按钮 / tag */
  --radius-sm: 4px;        /* 卡片 */
  --radius-md: 8px;
  --radius-lg: 12px;       /* 仅特殊场景 */
  --radius-pill: 999px;
}
```

#### 3.2.6 Shadows

```css
:root {
  --shadow-none: none;
  --shadow-sm: 0 1px 2px rgba(42, 36, 32, 0.06);
  --shadow-md: 0 4px 12px rgba(42, 36, 32, 0.08);
  --shadow-lg: 0 12px 32px rgba(42, 36, 32, 0.12);
  --shadow-focus: 0 0 0 3px rgba(169, 76, 44, 0.25);
}
```

#### 3.2.7 Motion

```css
:root {
  --ease-museum: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
  --duration-cinematic: 1200ms;   /* Tour 打字机、幕布动画 */
}
```

#### 3.2.8 Breakpoints

```css
:root {
  --bp-xs: 0px;
  --bp-sm: 640px;
  --bp-md: 768px;
  --bp-lg: 1024px;
  --bp-xl: 1280px;
}
```

JS 端也需要同步(用于 ResizeObserver / window.matchMedia 逻辑判断),在 `design-system/tokens/breakpoints.js` 导出同名常量。

### 3.3 SVG 母题组件

#### 3.3.1 组件 API 统一规范

每个母题 SFC 必须支持:

```vue
<FishFaceSymbol
  :size="120"                                 <!-- number|string,默认 24 -->
  :color="var(--color-accent)"                <!-- 默认 currentColor -->
  :stroke-width="2"                           <!-- 线条类母题需要 -->
  variant="outline"                           <!-- 可选:outline/filled/both -->
  aria-label="半坡人面鱼纹"
/>
```

**母题组件无外部依赖**(不引入 `@element-plus/icons-vue`),返回内联 `<svg>`,颜色默认 `currentColor` 以便父组件 CSS `color` 控制。

> 注:`@element-plus/icons-vue` 在其它场景(如 AppHeader 的导航 icon `ChatDotRound` `Compass` `Collection`)继续使用 —— 母题 SVG 与 UI icon 是两类资产,互不替代。

#### 3.3.2 母题清单

| 组件 | 分类 | 用途 |
|---|---|---|
| `FishFaceSymbol` | 符号 | 首页 hero、Tour onboarding 顶部、登录对话框 brand mark、favicon |
| `FishSwim` | 符号 | SectionDivider 中心、加载动画 |
| `RopePattern` | 纹样 | 页面背景水印(5-10% 透明)、卡片底纹 |
| `NetPattern` | 纹样 | Tour 报告页装饰带 |
| `TrianglePattern` | 纹样 | HallSelect 卡片角饰、Admin 表头 |
| `PointedJar` | 器物 | 404 / 空状态(图书/陶瓷展品) |
| `FishFaceBasin` | 器物 | 空状态(展品浏览) |
| `ClayPot` | 器物 | 空状态(问答无会话) |

### 3.4 封装组件

#### 3.4.1 MuseumPage.vue — 统一页面骨架

```vue
<MuseumPage>
  <template #breadcrumb>
    <!-- 可选,路径面包屑 -->
  </template>
  <template #hero>
    <!-- 可选,大标题 + 副标题 -->
  </template>
  <template #sidebar>
    <!-- 可选,页面内二级侧边栏(不是 AppSidebar) -->
  </template>
  <!-- 主内容 -->
</MuseumPage>
```

结构:

```
┌────────────────────────────────────────┐
│ [breadcrumb slot]                      │  ← caption label, 铜金分隔
├────────────────────────────────────────┤
│                                        │
│         [hero slot]                    │  ← display 字号,可选 SVG 水印
│                                        │
│── <SectionDivider /> ────────────────  │
│                                        │
│  [default slot = main content]         │
│                                        │
└────────────────────────────────────────┘
```

#### 3.4.2 MuseumCard

```vue
<MuseumCard
  title="展品名"
  subtitle="战国 · 陶器"
  :accent="true"            <!-- 顶部是否加铜金细线 -->
  :motif="'jar'"            <!-- 可选装饰母题 -->
  variant="elevated"        <!-- flat | outlined | elevated -->
>
  内容
</MuseumCard>
```

#### 3.4.3 MuseumButton

Variants:
- `primary` — 赭红实底 + 素麻白字
- `secondary` — 素麻白底 + 陶墨字 + 陶墨描边
- `ghost` — 无底,陶墨字,hover 显示铜金下划线
- `text` — 纯文字,下划线 hover

Sizes: `sm | md | lg`。默认 `md`。

另含 `fullWidth` boolean prop(默认 false),启用时 `width: 100%`,用于登录对话框等需要 CTA 占满容器宽度的场景。

#### 3.4.4 MuseumDialog

基于 `el-dialog` 封装,改:
- 顶部区高度 60px,bottom 加 1px 铜金线分隔
- header 标题用 serif + h3 字号
- body padding 统一 --space-8
- footer 右对齐按钮组,按钮间距 --space-3
- 移动端 <768 自动变 `fullscreen`

#### 3.4.5 SectionDivider

```vue
<SectionDivider :ornament="true" />  <!-- 中心显示 FishSwim SVG -->
<SectionDivider />                    <!-- 纯铜金细线 -->
```

#### 3.4.6 EmptyState

```vue
<EmptyState
  icon="jar"                    <!-- jar | basin | fish -->
  title="这里还没有文物"
  description="点击左侧筛选器开始探索"
>
  <MuseumButton>开始</MuseumButton>
</EmptyState>
```

#### 3.4.7 AppDrawer(移动端侧边栏抽屉)

基于 `el-drawer` 封装,左侧滑入,内容与桌面 sidebar 一致。由 AppHeader 的 hamburger 按钮触发。

### 3.5 Element Plus 主题覆盖

`element-theme.css`:

```css
:root {
  /* 把 Element Plus 的语义色重新指向 museum tokens */
  --el-color-primary: var(--color-accent);
  --el-color-primary-light-3: var(--color-accent-soft);
  --el-color-primary-light-5: var(--color-accent-muted);
  --el-color-primary-dark-2: var(--color-accent-hover);

  --el-color-success: var(--color-jade);
  --el-color-warning: var(--color-gold-line);
  --el-color-danger: var(--color-danger);
  --el-color-info: var(--color-text-muted);

  --el-text-color-primary: var(--color-text-primary);
  --el-text-color-regular: var(--color-text-primary);
  --el-text-color-secondary: var(--color-text-secondary);
  --el-text-color-placeholder: var(--color-text-muted);

  --el-bg-color: var(--color-bg-base);
  --el-bg-color-page: var(--color-bg-base);
  --el-fill-color: var(--color-bg-subtle);
  --el-fill-color-light: var(--color-surface-card);

  --el-border-color: var(--color-border);
  --el-border-color-light: var(--color-border);
  --el-border-radius-base: var(--radius-sm);

  --el-font-family: var(--font-family-body);
}
```

这一层保证了 `el-table / el-form / el-menu / el-dialog / el-tag / el-tabs` 等**全部内置组件**自动跟随主题色,不必逐一重写。

---

## 4. 布局与导航重构

### 4.1 App.vue 改造

```vue
<script setup>
const route = useRoute()
const isTourMode = computed(() => route.path.startsWith('/tour'))
const isMobile = useMediaQuery('(max-width: 767px)')
const drawerOpen = ref(false)

// 根据 route meta 决定侧边栏类型
const sidebarType = computed(() => route.meta.sidebar || null)
</script>

<template>
  <div class="app-container" :data-theme="isTourMode ? 'tour-dark' : 'default'">
    <AppHeader
      v-if="!isTourMode"
      :show-hamburger="isMobile && sidebarType"
      @toggle-drawer="drawerOpen = !drawerOpen"
    />
    <div class="app-body">
      <!-- 桌面: 永驻 sidebar -->
      <AppSidebar
        v-if="!isTourMode && sidebarType && !isMobile"
        :type="sidebarType"
      />
      <!-- 移动: 抽屉 sidebar -->
      <AppDrawer
        v-if="!isTourMode && sidebarType && isMobile"
        v-model:open="drawerOpen"
        :type="sidebarType"
      />
      <main class="app-main" :class="{ 'tour-mode': isTourMode }">
        <router-view ... />
      </main>
    </div>
  </div>
</template>
```

`useMediaQuery` 是一个轻量 composable(自实现 / 或从 `@vueuse/core` 引入 —— 项目当前未用 vueuse,用 **自实现** 避免引入新依赖)。

### 4.2 Router meta 策略

```js
// router/index.js
{ path: '/',         meta: { sidebar: 'chat-sessions' } }
{ path: '/exhibits', meta: { sidebar: 'exhibit-filters' } }
{ path: '/curator',  meta: { sidebar: 'tour-plan' } }
{ path: '/profile',  meta: { sidebar: null } }          /* 去 sidebar */
{ path: '/tour',     meta: { sidebar: null } }          /* 特殊,全屏 */
{ path: '/admin',    meta: { sidebar: 'admin-nav' }, children: [...] }
```

`AppSidebar.vue` 成为薄壳,根据 `props.type` 动态渲染对应子组件:

```vue
<template>
  <aside class="app-sidebar">
    <ChatSessionsSidebar  v-if="type === 'chat-sessions'" />
    <ExhibitFilterSidebar v-else-if="type === 'exhibit-filters'" />
    <TourPlanSidebar      v-else-if="type === 'tour-plan'" />
    <AdminNavSidebar      v-else-if="type === 'admin-nav'" />
  </aside>
</template>
```

### 4.3 侧边栏各模式内容

#### 4.3.1 ChatSessionsSidebar
- 顶部 "+ 新建会话" MuseumButton primary
- 会话列表(从 `useChat()` composable 取,不再从 ChatPanel 内部)
- 每项:标题 + 创建时间 + hover 露出删除按钮
- 空状态:ClayPot SVG + "暂无会话,开始你的第一次对话吧"

#### 4.3.2 ExhibitFilterSidebar
- 从 `ExhibitsView` 抽出 `ExhibitFilter.vue` 组件,直接嵌入
- 顶部 SectionDivider + label "筛选"
- 筛选变更通过 `emit('filter', filters)` → 现有 useExhibits composable

#### 4.3.3 TourPlanSidebar
- 折叠面板上下两块:
  - 上:当前 TourPlanner 表单(时间 slider + 兴趣 checkbox + 规划按钮)
  - 下:规划结果 TourPathView(展品顺序列表,点击 emit select-exhibit)
- 从 CuratorView 抽出,主内容区专注地图 + 详情

#### 4.3.4 AdminNavSidebar
- 保持当前 el-menu 结构,5 个菜单项
- 菜单项改 serif 字体
- 激活项:左侧 3px 赭红实色条 + 背景 `--color-bg-subtle`
- hover:铜金底部细线

### 4.4 AppHeader 改造

```
高度 60px
├── 左:Logo 区
│   └── <FishFaceSymbol size="28" /> + serif"MuseAI · 半坡博物馆"
├── 中:导航 menu(el-menu mode="horizontal")
│   ├── 每项:icon + serif 字
│   ├── hover:4px 铜金底部下划线
│   └── active:4px 赭红底部下划线
└── 右:
    ├── 健康状态 el-tag
    ├── 用户下拉 or 登录按钮(MuseumButton primary)
    └── [mobile] hamburger 按钮(只在 isMobile && hasSidebar 时显示)

底部:1px 铜金细线 --color-gold-line
```

---

## 5. 页面重设计

### 5.1 首页 `/` 智能问答(HomeView.vue)

**结构**:

```
<MuseumPage>
  <template #hero>
    <div class="home-hero">
      <FishFaceSymbol size="56" color="var(--color-accent)" style="水印" />
      <h1>与半坡对话</h1>
      <p class="subtitle">六千年的陶土之下,每一个疑问都值得追问</p>
      <MuseumButton variant="primary" @click="startTour">开启 AI 导览 →</MuseumButton>
    </div>
  </template>

  <!-- 主内容 -->
  <ChatMainArea />   <!-- 重构版 ChatPanel,去掉内置 sessions 列表 -->
</MuseumPage>
```

**ChatPanel 重构**(改名 `ChatMainArea.vue`):
- 去除 250px 内嵌会话列表(移到 AppSidebar)
- 移除所有 inline style,改 scoped CSS 使用 tokens
- 消息气泡:
  - user:右侧,背景 `--color-accent`,字色 `--color-text-inverse`,圆角 `--radius-sm`
  - assistant:左侧,背景 `--color-surface-card`,字色 `--color-text-primary`,顶部 4px 铜金细线
- RAG 步骤思考气泡:背景 `rgba(90,122,107,0.1)`(陶青淡色),标题 `--color-jade`
- 输入框:底部粘性,细金线上边框,无多余边框
- 空状态(无消息时):FishSwim SVG + "开始你的第一次提问"

### 5.2 展品浏览 `/exhibits` (ExhibitsView.vue)

- 去除 `el-row :span="6/18"` 布局(筛选器移到 sidebar)
- 主内容全宽 `el-tabs`:列表视图 / 地图视图
- ExhibitList 卡片升级为 MuseumCard:
  - 顶部 4px 铜金细线(accent=true)
  - **图片区从现有的固定 160px 高度改为 16:9 aspect-ratio**(与现代策展卡片惯例一致,保留图片比例)
  - 无图时展示对应 motif(category 映射:`陶器→ClayPot`, `艺术→FishFaceBasin`, 其它→PointedJar)
  - 标题 serif h4
  - 副文:category tag(el-tag 继承主题自动变色) + era + location
- 地图视图(FloorMap):
  - 背景 `--color-bg-base` 素麻白
  - 栅格线 `--color-border` 淡陶
  - 路径线:`--color-accent` 赭红虚线
  - 标点:circle radius 10,filled with `--color-accent` / `--color-jade` / `--color-danger`
- 响应式 <768:sidebar 变抽屉,卡片单列

### 5.3 导览助手 `/curator` (CuratorView.vue)

- 布局改为:sidebar (TourPlanSidebar) + 主内容(FloorMap + ExhibitDetail)
- 主内容 `el-row`:左 FloorMap 18 / 右 ExhibitDetail 6(桌面),<1024 改为上下堆叠
- ExhibitDetail MuseumCard:
  - 顶部 FishFaceSymbol size=32 水印
  - 叙事卡片:`--font-family-serif` + 行高 2.0
  - 思考引导列表:每项前缀用 FishSwim size=12 SVG 代替 bullet

### 5.4 个人设置 `/profile` (ProfileSettings.vue)

- `meta.sidebar = null` → 无 sidebar,主内容全宽
- 居中 `max-width: 640px`
- MuseumCard 分段:
  - 兴趣偏好 · 知识水平 · 叙事偏好 · 反思深度
  - 每段之间 SectionDivider
- el-checkbox-group 自动继承 `--el-color-primary` 变赭红
- 保存按钮:MuseumButton primary 固定底部

### 5.5 AI 导览 `/tour` (TourView.vue)

**交互不变**(OnboardingQuiz → OpeningNarrative → HallSelect → ExhibitTour → TourReport)。

**视觉层替换**:

| 子组件 | 改动 |
|---|---|
| `tour-container` | 背景 `--color-bg-base`(dark 变体 = #2a1f18);字色 `--color-text-primary` = #f0e6d3 |
| `OnboardingQuiz` | 顶部加 `<FishFaceSymbol size="72" />` + 铜金 SectionDivider;option-card hover 色从 `rgba(212,165,116,0.15)` → `rgba(196,122,82,0.2)` |
| `OpeningNarrative` | persona badge 保留;narrative-text 右下角加淡化 ClayPot SVG 水印 `opacity: 0.08` |
| `HallSelect` | hall-card 角饰:左上加 TrianglePattern SVG(5% 透明);emoji (🏺🏚️) 换用 FishFaceBasin/ClayPot SVG |
| `ExhibitTour` / `ExhibitChat` | 消息气泡沿用原样 + token 化;suggestions card 背景加绳纹 pattern 低透明 |
| `TourReport` | report-header 顶部加一整道 NetPattern 装饰带;theme-A/B/C 背景沿用原梯度,叠加淡陶底 |

**Tour 响应式** <768:
- OnboardingQuiz options 强制单列
- HallSelect cards 单列
- ExhibitChat 输入框 sticky bottom
- 字号降 2px

### 5.6 管理后台 `/admin/*` (轻量适配)

**不改业务结构**,仅:
- 所有 `el-table`:表头字体 serif,背景 `--color-bg-subtle`,row hover 背景 `--color-accent-muted`
- 所有 `el-form`:label 字体 serif,input 底部边框赭红 focus
- 所有 `el-dialog`:自动继承 MuseumDialog 主题(通过 element-theme.css)
- `AdminNavSidebar`:见 4.3.4
- 各 Manager 页空状态:换 EmptyState 组件

---

## 6. 交互细节

### 6.1 登录/注册对话框 (`AuthModal.vue` → `MuseumDialog`)

**结构**:

```
┌──────────────────────────────────────┐
│  [FishFaceSymbol size=64]            │  ← 居中 brand mark
│                                      │
│        欢迎回到半坡                   │  ← h2 serif
│   ————————(铜金细线)————————          │
│                                      │
│  ┌─ 登录 ─────── 注册 ───┐           │  ← Tabs
│  │                        │           │
│  │  邮箱 ________________ │           │  ← 无边框 + 底部 1px 边框
│  │  密码 ________________ │           │
│  │                        │           │
│  │  [登录] MuseumButton   │           │  ← 赭红实底,full-width
│  └────────────────────────┘           │
└──────────────────────────────────────┘
```

- Input focus:底部边框从 --color-border → --color-accent
- Tab 激活:底部 2px 赭红线
- 移动端 <768:变 fullscreen

### 6.2 空状态 / 404

- **`EmptyState.vue`** 组件替换全站所有 `el-empty`
- **`404View.vue`** 新增路由 `/:pathMatch(.*)*`,展示大号破碎 PointedJar SVG + "此处无文物" + "返回首页" 按钮

### 6.3 index.html 元信息

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#a94c2c">
  <meta name="description" content="沉浸式 AI 博物馆导览系统 —— 与半坡新石器时代展开对话">
  <title>MuseAI · 半坡博物馆智能导览</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
</head>
```

`favicon.svg`:简化版 FishFaceSymbol,单色赭红 `#a94c2c`,置于 `frontend/public/favicon.svg`(vite 会 copy)。

### 6.4 Design System 预览页 `/design-system`

新路由(所有环境可见,非 admin-only),`DesignSystemView.vue` 单页展示:

- **Colors**:所有 token 色彩 swatch + HEX + 变量名
- **Typography**:字号 + 行高 + 字族 样本(each includes 汉字 + 英文 + 数字)
- **Spacing**:ruler 可视化
- **Motifs**:所有 SVG 组件展示,含 props 示例
- **Components**:MuseumCard / Button / Dialog / EmptyState 各变体
- **Icons from Element Plus**:项目中实际使用的 icon 列表

作为内部文档 + 设计稿 + 回归参考。

---

## 7. 响应式策略

### 7.1 断点

| 名称 | 范围 | 目标设备 |
|---|---|---|
| xs | <640 | 手机竖屏 |
| sm | 640–767 | 手机横屏 / 小平板竖 |
| md | 768–1023 | 平板 |
| lg | 1024–1279 | 小笔记本 |
| xl | >=1280 | 桌面(原设计目标) |

### 7.2 侧边栏

- **>=768**:永驻侧边栏,260px 宽
- **<768**:侧边栏变 AppDrawer 抽屉,由 AppHeader 左上 hamburger 触发

### 7.3 栅格适配

- 展品卡片 el-col:xs=24 / sm=12 / md=8(桌面 3 列)
- 管理后台表格:在 <768 改 `el-scrollbar` 横向滚动,保留完整列

### 7.4 字号适配

在 `typography.css` 加 media:

```css
@media (max-width: 767px) {
  :root {
    --font-size-display: 36px;   /* 从 48 降 */
    --font-size-h1: 26px;
    --font-size-h2: 20px;
    --font-size-body: 14px;
  }
}
```

### 7.5 Tour 移动端

- `.tour-container` 改 `min-height: 100dvh`(dvh > vh,兼容浏览器 URL 栏)
- 各步骤 padding 从 40px/20px 减到 24px/12px
- OnboardingQuiz / HallSelect 强制单列
- ExhibitChat 输入区 `position: sticky; bottom: 0`
- OpeningNarrative 文字 max-width 100%,行高保持 2.0
- Tour 的 `--font-size-body` 移动端不额外降(7.4 的全局降级已覆盖);`--font-size-h1` 从 26px 再降至 22px

---

## 8. 三阶段 PR 交付节奏

### Phase 1 · 设计系统骨架(预估 1500 行)

**目标**:design system 完全就绪,全站视觉开始呈现博物馆感,但功能布局未变。

| 交付物 |
|---|
| `design-system/tokens/**`(全部 token 文件) |
| `design-system/fonts/source-han-serif/`(WOFF2 自托管 + @font-face) |
| `design-system/motifs/**`(8 个 SVG SFC + index 导出) |
| `design-system/components/{MuseumCard, MuseumButton, MuseumDialog, MuseumInput, SectionDivider, EmptyState, MuseumPage}.vue` |
| `design-system/element-theme.css` |
| `design-system/index.css` + `main.js` 导入 |
| `DesignSystemView.vue` + route `/design-system` |
| `index.html` 元信息 / favicon.svg |
| `App.vue` + `AppHeader.vue` 最小改造(logo 换 FishFaceSymbol,加铜金线) |

**验收**:
1. 访问 `/design-system`,所有 token / 母题 / 组件可视
2. 现有所有页面在视觉上已应用字体 + 主色赭红,el-button / el-menu / el-tag 自动变色
3. favicon 为人面鱼纹,页面 title 正确

### Phase 2 · 侧边栏重构 + 核心前台页面(预估 2000 行)

**目标**:问答 / 展品 / 导览助手 / 个人设置 全部迁移到新 design system,侧边栏变有用,登录对话框重做,全面移动端适配。

| 交付物 |
|---|
| `router/index.js` 加 `meta.sidebar` |
| `AppSidebar.vue` 重写为薄壳 |
| `components/layout/sidebars/{ChatSessions, ExhibitFilter, TourPlan, AdminNav}Sidebar.vue` |
| `useMediaQuery` composable |
| `AppDrawer.vue`(移动抽屉) |
| `HomeView.vue` + `ChatMainArea.vue`(ChatPanel 重构) |
| `ExhibitsView.vue`(去 el-row 改全宽 tabs) |
| `CuratorView.vue`(去 TourPlanner / TourPathView 从主内容,移到 sidebar) |
| `ProfileSettings.vue`(居中单栏) |
| `AuthModal.vue` 重做 → MuseumDialog |
| `404View.vue` + catch-all route |
| 全站 `el-empty` 替换为 `EmptyState` |
| 所有前台页 media query 完备 |

**验收**:
1. `/` `/exhibits` `/curator` `/profile` 视觉统一,侧边栏内容真正有用
2. 登录对话框新设计,mobile 为全屏
3. <768 屏宽下所有页可用,sidebar 为抽屉
4. 访问不存在路径展示 404View(陶罐 SVG)

### Phase 3 · Tour 配色迁移 + Admin 适配 + 细节(预估 1000 行)

**目标**:Tour 视觉纳入同一设计系统(暗版);管理后台应用 tokens + 字体;收尾所有细节。

| 交付物 |
|---|
| `App.vue` 加 `data-theme` 切换逻辑 |
| `TourView.vue` 配色全部改用 tokens |
| Tour 各子组件(OnboardingQuiz / OpeningNarrative / HallSelect / HallIntro / ExhibitTour / ExhibitChat / ExhibitNavigator / TourReport / RadarChart / IdentityTags / TourOneLiner / TourStats)配色替换 |
| Tour 装饰 SVG 注入:OnboardingQuiz 顶部人面鱼纹、HallSelect 三角纹角饰、TourReport 绳纹装饰带 |
| Tour 各页响应式(强制单列、输入框 sticky) |
| `AdminView.vue` + 5 个 Manager 子页 token 适配 |
| `AdminNavSidebar` 风格化完成 |
| `el-table` / `el-form` / `el-dialog` 全站样式检查 |
| Tour 的 emoji → SVG 替换(opt-in,可延到下一期) |
| 手动回归:5 个前台 + 5 个 admin + 5 个 Tour 步骤,每个在 1280 / 768 / 375 三档截图对照,确认无错位 |

**验收**:
1. `/tour` 访问体验完全延续,但配色属于同一 design system 暗版
2. `/admin/*` 视觉与前台统一,功能无回归
3. 所有 SVG 母题在实际页面中至少出现一次(非仅 design-system 预览)

---

## 9. 验收标准(全局)

- [ ] 所有组件使用 design-system tokens,grep 不到硬编码颜色(`#xxx` 仅允许出现在 design-system 目录内)
- [ ] 侧边栏每个模式都有真实功能,无任何静态占位文案
- [ ] Tour 与其它页视觉属于同一 token 系统(light + dark 变体)
- [ ] mobile (<768) 全页面可用,无横向滚动,sidebar 为抽屉
- [ ] SVG 母题 8 个组件完整,design-system 预览页完整展示
- [ ] `index.html` 元信息更新,favicon 到位
- [ ] 登录/注册新样式 + 所有 `el-empty` 换 `EmptyState`
- [ ] 已有测试(backend + frontend 单测)全部通过
- [ ] Bundle 体积增加不超过 300KB(主要来自自托管字体,其它 CSS/SVG 可忽略)

---

## 10. 开放问题与风险

### 10.1 字体体积

Source Han Serif CN 即便子集化后 Regular + SemiBold 两重也约 1.6MB。缓解方案:
- 仅加载 Regular(400),SemiBold 用 CSS `font-synthesis: weight` 合成(质量略降)
- 或首屏仅加载 Regular,SemiBold 异步加载
- 最终方案在 Phase 1 实施时根据实际字重采样决定

### 10.2 既有测试兼容

`frontend/src/components/layout/__tests__/` / `components/profile/__tests__/` / `composables/__tests__/` / `api/__tests__/` 都有单测。重构组件时必须保持原 public API(prop / emit / slot),避免动测试。如必须改测试,在 PR 中单独标注。

### 10.3 颜色对比度 a11y

赭红 `#a94c2c` 在素麻白 `#f5eedc` 上的对比度需测算是否达到 WCAG AA(4.5:1)。预判:text 场景可能接近 4.8:1,通过;small text 要警惕。Phase 1 验收时用 axe/lighthouse 自查。

### 10.4 打字机兼容暗主题

Tour OpeningNarrative 的打字机 `setInterval` 实现,迁移配色后视觉上应无影响,但光标 `#d4a574` 需确认在 `#2a1f18` 上可见。

### 10.5 Element Plus 版本锁定

`element-theme.css` 基于 Element Plus 2.13.6 的 CSS 变量命名。如未来升级 Element Plus 大版本,需回归检查。

---

## 11. 目录外变更清单

项目根新增 / 修改:

- `.gitignore`:已添加 `.superpowers/`(本次 brainstorm 副产物)
- `frontend/public/favicon.svg`(新)
- `frontend/index.html`(修)
- `frontend/src/main.js`(修,导入 design-system)
- `frontend/src/router/index.js`(修,加 meta.sidebar + 404 + /design-system 路由)
- `frontend/src/App.vue`(修)

---

## 12. 后续扩展(非本次范围)

- 深色模式全站切换(用户偏好)
- i18n 国际化(英文 / 日文)
- Storybook 替代 `DesignSystemView`(当生态扩大后)
- emoji → SVG 图标全量替换(Phase 3 可能延期)
- 移动端 PWA 可安装化
- 动态主题(如根据展览季节切换色板)
