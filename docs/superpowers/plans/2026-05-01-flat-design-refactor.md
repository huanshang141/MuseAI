# Flat Design Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the entire MuseAI frontend from "museum terracotta" aesthetic to flat design with fluid responsive scaling across mobile, 1080p, and 4K.

**Architecture:** Token-first cascade — modify CSS custom property tokens (colors, typography, spacing, radii, shadows, motion), then update Element Plus theme overrides, then simplify design system components, then flatten feature components. Changes to tokens cascade automatically through the Element Plus theme into all components.

**Tech Stack:** Vue 3, Element Plus, CSS custom properties, `clamp()` for fluid sizing

**Spec:** `docs/superpowers/specs/2026-05-01-flat-design-refactor-design.md`

---

## Task 1: Color Tokens

**Files:**
- Modify: `frontend/src/design-system/tokens/colors.css`

- [ ] **Step 1: Replace colors.css content**

Replace the entire file with the flat color palette. Remove the `data-theme="tour-dark"` block.

```css
:root {
  --color-bg-base: #ffffff;
  --color-bg-elevated: #f8f6f1;
  --color-bg-subtle: #f0ece3;
  --color-surface-card: #ffffff;

  --color-text-primary: #1a1816;
  --color-text-secondary: #3a3632;
  --color-text-muted: #6a6460;
  --color-text-faint: #9a9490;
  --color-text-inverse: #ffffff;

  --color-accent: #a94c2c;
  --color-accent-hover: #8f3f23;
  --color-accent-soft: #c47a52;
  --color-accent-muted: #e8d5a8;

  --color-jade: #5a7a6b;
  --color-jade-soft: #7a9588;
  --color-gold: #c89d5a;
  --color-danger: #8b2f1f;

  --color-border: #e8e2d6;
  --color-border-strong: #d9c9a8;
  --color-divider: #e8e2d6;

  --color-primary: var(--color-accent);
  --color-success: var(--color-jade);
  --color-warning: var(--color-gold);
  --color-info: var(--color-text-muted);
}
```

- [ ] **Step 2: Verify dev server renders**

Run: `cd frontend && npm run dev` and check that the app loads without visual breakage. Colors will look different but nothing should be broken.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/tokens/colors.css
git commit -m "refactor(tokens): flatten color palette, remove dark theme"
```

---

## Task 2: Typography Tokens

**Files:**
- Modify: `frontend/src/design-system/tokens/typography.css`

- [ ] **Step 1: Replace typography.css content**

Replace the entire file. Switch to sans-serif, add `clamp()` fluid sizes, remove the `@media (max-width: 767px)` block.

```css
:root {
  --font-family-base: 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-family-mono: 'JetBrains Mono', 'Fira Code', monospace;

  --font-size-display: clamp(2rem, 3.5vw + 0.5rem, 4.5rem);
  --font-size-h1: clamp(1.5rem, 2.5vw + 0.25rem, 3.25rem);
  --font-size-h2: clamp(1.25rem, 1.8vw + 0.25rem, 2.5rem);
  --font-size-h3: clamp(1.125rem, 1.2vw + 0.25rem, 1.875rem);
  --font-size-h4: clamp(1rem, 1vw + 0.25rem, 1.5rem);
  --font-size-body: clamp(0.875rem, 0.5vw + 0.625rem, 1.125rem);
  --font-size-body-sm: clamp(0.75rem, 0.3vw + 0.5625rem, 0.9375rem);
  --font-size-caption: clamp(0.6875rem, 0.2vw + 0.5625rem, 0.875rem);
  --font-size-label: clamp(0.625rem, 0.15vw + 0.5rem, 0.8125rem);

  --line-height-tight: 1.3;
  --line-height-normal: 1.6;
  --line-height-relaxed: 2;

  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
}
```

- [ ] **Step 2: Verify dev server renders**

Run: `cd frontend && npm run dev`. Text should render in sans-serif. Font sizes should be responsive — resize the browser window to verify scaling.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/tokens/typography.css
git commit -m "refactor(tokens): switch to sans-serif, add fluid clamp() typography"
```

---

## Task 3: Spacing Tokens

**Files:**
- Modify: `frontend/src/design-system/tokens/spacing.css`

- [ ] **Step 1: Add fluid spacing tokens**

Append fluid spacing tokens to the existing file. Keep all static tokens.

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

  --space-fluid-xs: clamp(0.5rem, 1vw, 1rem);
  --space-fluid-sm: clamp(0.75rem, 1.5vw, 1.5rem);
  --space-fluid-md: clamp(1rem, 2vw, 2.5rem);
  --space-fluid-lg: clamp(1.5rem, 3vw, 4rem);
  --space-fluid-xl: clamp(2rem, 4vw, 6rem);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/tokens/spacing.css
git commit -m "refactor(tokens): add fluid spacing scale"
```

---

## Task 4: Radii Tokens

**Files:**
- Modify: `frontend/src/design-system/tokens/radii.css`

- [ ] **Step 1: Simplify radii to 4 values**

Replace the file. Remove `--radius-xs`, `--radius-md`, `--radius-lg`.

```css
:root {
  --radius-none: 0;
  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-pill: 999px;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/tokens/radii.css
git commit -m "refactor(tokens): simplify radii to 4 values"
```

---

## Task 5: Shadow Tokens

**Files:**
- Modify: `frontend/src/design-system/tokens/shadows.css`

- [ ] **Step 1: Remove all shadows except focus ring**

Replace the file.

```css
:root {
  --shadow-none: none;
  --shadow-sm: none;
  --shadow-md: none;
  --shadow-lg: none;
  --shadow-focus: 0 0 0 2px rgba(169, 76, 44, 0.2);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/tokens/shadows.css
git commit -m "refactor(tokens): remove shadows, keep focus ring only"
```

---

## Task 6: Motion Tokens

**Files:**
- Modify: `frontend/src/design-system/tokens/motion.css`

- [ ] **Step 1: Shorten durations, remove cinematic**

Replace the file.

```css
:root {
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 100ms;
  --duration-normal: 150ms;
  --duration-slow: 250ms;
}
```

- [ ] **Step 2: Search for `--duration-cinematic` and `--ease-museum` references**

Run: `grep -r "duration-cinematic\|ease-museum" frontend/src/`

Replace any references with `--duration-slow` and `--ease-default` respectively.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/tokens/motion.css
git commit -m "refactor(tokens): shorten motion durations, remove cinematic"
```

---

## Task 7: Breakpoint Tokens — Add Container Widths

**Files:**
- Modify: `frontend/src/design-system/tokens/breakpoints.css`

- [ ] **Step 1: Add container width tokens**

Append to the existing file.

```css
:root {
  --bp-xs: 0px;
  --bp-sm: 640px;
  --bp-md: 768px;
  --bp-lg: 1024px;
  --bp-xl: 1280px;

  --content-width-sm: 640px;
  --content-width-md: 840px;
  --content-width-lg: 1200px;
  --content-width-full: 1440px;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/tokens/breakpoints.css
git commit -m "refactor(tokens): add container width tokens"
```

---

## Task 8: Element Plus Theme Overrides

**Files:**
- Modify: `frontend/src/design-system/element-theme.css`

- [ ] **Step 1: Update element-theme.css**

Replace the file. Map new tokens, add font-family-base alias, remove box-shadow overrides.

```css
:root {
  --el-color-primary: var(--color-accent);
  --el-color-primary-light-3: var(--color-accent-soft);
  --el-color-primary-light-5: var(--color-accent-muted);
  --el-color-primary-dark-2: var(--color-accent-hover);

  --el-color-success: var(--color-jade);
  --el-color-warning: var(--color-gold);
  --el-color-danger: var(--color-danger);
  --el-color-info: var(--color-text-muted);

  --el-text-color-primary: var(--color-text-primary);
  --el-text-color-regular: var(--color-text-secondary);
  --el-text-color-secondary: var(--color-text-muted);
  --el-text-color-placeholder: var(--color-text-faint);

  --el-bg-color: var(--color-bg-base);
  --el-bg-color-page: var(--color-bg-base);
  --el-bg-color-overlay: var(--color-bg-base);
  --el-fill-color: var(--color-bg-subtle);
  --el-fill-color-light: var(--color-bg-elevated);
  --el-fill-color-lighter: var(--color-bg-subtle);
  --el-fill-color-blank: var(--color-bg-base);

  --el-border-color: var(--color-border);
  --el-border-color-light: var(--color-border);
  --el-border-color-lighter: var(--color-border);
  --el-border-radius-base: var(--radius-sm);

  --el-font-family: var(--font-family-base);
  --el-font-size-base: var(--font-size-body);

  --el-box-shadow: none;
  --el-box-shadow-light: none;
  --el-box-shadow-lighter: none;
}
```

- [ ] **Step 2: Verify Element Plus components render**

Run: `cd frontend && npm run dev`. Check that buttons, inputs, dialogs, tables, and other Element Plus components render with the new flat style (no shadows, new border colors, sans-serif font).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/element-theme.css
git commit -m "refactor(theme): remap Element Plus overrides to flat tokens"
```

---

## Task 9: Global Layout Styles + App.vue Max-Width Container

**Files:**
- Modify: `frontend/src/styles/custom.css`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Update custom.css**

Replace the file. Use design tokens, add max-width container.

```css
.app-container {
  height: 100vh;
  height: 100svh;
  display: flex;
  flex-direction: column;
}

.app-header {
  height: 52px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-fluid-md);
  background: var(--color-bg-base);
  flex-shrink: 0;
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  max-width: min(var(--content-width-full), 100vw);
  margin: 0 auto;
  width: 100%;
}

.app-sidebar {
  width: 280px;
  border-right: 1px solid var(--color-border);
  background: var(--color-bg-elevated);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-base);
  min-width: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.logo-icon {
  font-size: var(--font-size-h3);
}
```

- [ ] **Step 2: Update App.vue style block**

In `App.vue`, update the `<style>` block (not scoped). Replace the existing styles:

```css
@import './styles/custom.css';

.app-main {
  overflow: auto;
  padding: var(--space-fluid-md);
  background: var(--color-bg-base);
}

.app-main--no-padding {
  padding: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-slow) var(--ease-default);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 767px) {
  .app-main {
    padding: var(--space-3);
  }
}
```

- [ ] **Step 3: Verify layout renders**

Run: `cd frontend && npm run dev`. Check that the header, sidebar, and main content area render correctly. The sidebar should be 280px, the main area should have proper padding, and the app-body should be centered on wide screens.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/custom.css frontend/src/App.vue
git commit -m "refactor(layout): add max-width container, use design tokens"
```

---

## Task 10: MuseumButton — Simplify Variants

**Files:**
- Modify: `frontend/src/design-system/components/MuseumButton.vue`

- [ ] **Step 1: Replace MuseumButton.vue**

Replace the entire file. Remove ghost variant, simplify to primary/secondary/text.

```vue
<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'text'].includes(value),
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value),
  },
  fullWidth: { type: Boolean, default: false },
})
</script>

<template>
  <el-button
    class="museum-button"
    :class="[`is-${variant}`, `is-${size}`, { 'is-full': fullWidth }]"
    v-bind="$attrs"
  >
    <slot />
  </el-button>
</template>

<style scoped>
.museum-button {
  border-radius: var(--radius-sm);
}

.museum-button.is-full {
  width: 100%;
}

.museum-button.is-primary {
  --el-button-bg-color: var(--color-accent);
  --el-button-border-color: var(--color-accent);
  --el-button-text-color: var(--color-text-inverse);
  --el-button-hover-bg-color: var(--color-accent-hover);
  --el-button-hover-border-color: var(--color-accent-hover);
  --el-button-hover-text-color: var(--color-text-inverse);
}

.museum-button.is-secondary {
  --el-button-bg-color: transparent;
  --el-button-border-color: var(--color-border);
  --el-button-text-color: var(--color-accent);
  --el-button-hover-bg-color: var(--color-bg-subtle);
  --el-button-hover-border-color: var(--color-accent);
  --el-button-hover-text-color: var(--color-accent);
}

.museum-button.is-text {
  --el-button-bg-color: transparent;
  --el-button-border-color: transparent;
  --el-button-text-color: var(--color-accent);
  --el-button-hover-bg-color: transparent;
  --el-button-hover-border-color: transparent;
  --el-button-hover-text-color: var(--color-accent-hover);
}

.museum-button.is-sm {
  --el-button-padding-horizontal: var(--space-3);
}

.museum-button.is-lg {
  --el-button-padding-horizontal: var(--space-6);
}
</style>
```

- [ ] **Step 2: Search for `is-ghost` usage**

Run: `grep -r "is-ghost\|ghost" frontend/src/ --include="*.vue" --include="*.js"`

If any component uses the `ghost` variant, change it to `text` (the closest equivalent).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/components/MuseumButton.vue
git commit -m "refactor(button): simplify to primary/secondary/text variants"
```

---

## Task 11: MuseumCard — Remove Decorations

**Files:**
- Modify: `frontend/src/design-system/components/MuseumCard.vue`

- [ ] **Step 1: Replace MuseumCard.vue**

Replace the entire file. Remove motif imports, accent bar, variant complexity.

```vue
<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <article class="museum-card">
    <header v-if="title || subtitle" class="museum-card-header">
      <h3 v-if="title" class="museum-card-title">{{ title }}</h3>
      <p v-if="subtitle" class="museum-card-subtitle">{{ subtitle }}</p>
    </header>
    <div class="museum-card-content">
      <slot />
    </div>
  </article>
</template>

<style scoped>
.museum-card {
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.museum-card-header {
  padding: var(--space-4) var(--space-4) 0;
}

.museum-card-title {
  margin: 0;
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  font-family: var(--font-family-base);
}

.museum-card-subtitle {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-body-sm);
  color: var(--color-text-muted);
}

.museum-card-content {
  padding: var(--space-4);
}
</style>
```

- [ ] **Step 2: Search for MuseumCard usage with removed props**

Run: `grep -rn "MuseumCard\|<museum-card" frontend/src/ --include="*.vue"`

Check all usages. Remove `accent`, `motif`, `variant` props from call sites. Example fix:

```html
<!-- Before -->
<MuseumCard title="展品" :accent="true" motif="jar" variant="elevated">

<!-- After -->
<MuseumCard title="展品">
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/components/MuseumCard.vue
git commit -m "refactor(card): remove motif decorations and accent bar"
```

---

## Task 12: MuseumDialog — Simplify

**Files:**
- Modify: `frontend/src/design-system/components/MuseumDialog.vue`

- [ ] **Step 1: Update MuseumDialog.vue styles**

Update only the `<style scoped>` section. Keep the script and template as-is.

```vue
<style scoped>
.museum-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid var(--color-divider);
  margin: 0;
  padding: var(--space-4) var(--space-6);
}

.museum-dialog :deep(.el-dialog__title) {
  font-family: var(--font-family-base);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-semibold);
}

.museum-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.museum-dialog :deep(.el-dialog) {
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.museum-dialog-body {
  padding: var(--space-6);
}

.museum-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/components/MuseumDialog.vue
git commit -m "refactor(dialog): flatten styling, use design tokens"
```

---

## Task 13: MuseumInput — Simplify

**Files:**
- Modify: `frontend/src/design-system/components/MuseumInput.vue`

- [ ] **Step 1: Update MuseumInput.vue styles**

Update the `<style scoped>` section.

```vue
<style scoped>
.museum-input :deep(.el-input__wrapper) {
  border-radius: var(--radius-sm);
  box-shadow: none;
  border: 1px solid var(--color-border);
}

.museum-input :deep(.el-input__wrapper:hover) {
  border-color: var(--color-border-strong);
}

.museum-input :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-accent);
  box-shadow: none;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/components/MuseumInput.vue
git commit -m "refactor(input): flatten focus state, remove glow"
```

---

## Task 14: MuseumPage — Remove Hero/Decorations

**Files:**
- Modify: `frontend/src/design-system/components/MuseumPage.vue`

- [ ] **Step 1: Replace MuseumPage.vue**

Replace the entire file. Remove hero slot, divider slot. Keep breadcrumb + content.

```vue
<template>
  <section class="museum-page">
    <div v-if="$slots.breadcrumb" class="museum-page-breadcrumb">
      <slot name="breadcrumb" />
    </div>

    <div class="museum-page-content">
      <aside v-if="$slots.sidebar" class="museum-page-sidebar">
        <slot name="sidebar" />
      </aside>
      <div class="museum-page-main">
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.museum-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-fluid-md);
}

.museum-page-breadcrumb {
  font-size: var(--font-size-caption);
  color: var(--color-text-muted);
}

.museum-page-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-fluid-md);
}

@media (min-width: 1024px) {
  .museum-page-content {
    grid-template-columns: auto 1fr;
  }
}
</style>
```

- [ ] **Step 2: Search for hero/divider slot usage**

Run: `grep -rn "#hero\|#divider\|v-slot:hero\|v-slot:divider" frontend/src/ --include="*.vue"`

Remove any `template #hero` or `template #divider` slots from call sites.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/components/MuseumPage.vue
git commit -m "refactor(page): remove hero and divider slots"
```

---

## Task 15: SectionDivider — Simplify to Plain Line

**Files:**
- Modify: `frontend/src/design-system/components/SectionDivider.vue`

- [ ] **Step 1: Replace SectionDivider.vue**

Replace the entire file. Remove FishSwim ornament.

```vue
<template>
  <div class="section-divider" />
</template>

<style scoped>
.section-divider {
  width: 100%;
  height: 1px;
  background: var(--color-divider);
}
</style>
```

- [ ] **Step 2: Search for `ornament` prop usage**

Run: `grep -rn "ornament" frontend/src/ --include="*.vue"`

Remove any `ornament` prop from call sites.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/components/SectionDivider.vue
git commit -m "refactor(divider): simplify to plain 1px line"
```

---

## Task 16: EmptyState — Remove Motif Icons

**Files:**
- Modify: `frontend/src/design-system/components/EmptyState.vue`

- [ ] **Step 1: Replace EmptyState.vue**

Replace the entire file. Use Element Plus icon instead of motif SVGs.

```vue
<script setup>
import { Box } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})
</script>

<template>
  <div class="empty-state">
    <el-icon :size="48" class="empty-icon"><Box /></el-icon>
    <h3 v-if="title" class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8);
  text-align: center;
  color: var(--color-text-muted);
}

.empty-icon {
  color: var(--color-text-faint);
}

.empty-title {
  margin: 0;
  font-size: var(--font-size-h4);
  color: var(--color-text-primary);
}

.empty-description {
  margin: 0;
  font-size: var(--font-size-body);
}

.empty-actions {
  margin-top: var(--space-2);
}
</style>
```

- [ ] **Step 2: Search for EmptyState `icon` prop usage**

Run: `grep -rn "EmptyState" frontend/src/ --include="*.vue"`

Remove any `icon` prop from call sites (the prop no longer exists).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/design-system/components/EmptyState.vue
git commit -m "refactor(empty-state): replace motifs with Element Plus icon"
```

---

## Task 17: AppHeader — Flat Styling

**Files:**
- Modify: `frontend/src/components/layout/AppHeader.vue`

- [ ] **Step 1: Update AppHeader.vue styles**

Update the `<style scoped>` section. Remove `--font-family-display`, use `--font-family-base`.

Replace the entire `<style scoped>` block:

```vue
<style scoped>
.app-header {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.nav-menu {
  min-width: 0;
  border-bottom: none;
  background: transparent;
}

.logo-mark {
  color: var(--color-accent);
}

.logo-title {
  font-family: var(--font-family-base);
  font-weight: var(--font-weight-semibold);
}

.nav-menu .el-menu-item {
  font-size: var(--font-size-body);
}

.nav-menu .el-menu-item.is-disabled {
  opacity: 0.5;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
}

.user-text {
  font-size: var(--font-size-body);
}

.sidebar-toggle {
  color: var(--color-text-primary);
}

@media (max-width: 767px) {
  .app-header {
    gap: var(--space-2);
  }

  .nav-menu {
    display: none;
  }

  .logo-title {
    font-size: var(--font-size-body);
  }

  .header-actions .el-tag {
    display: none;
  }

  .user-text {
    display: none;
  }
}
</style>
```

- [ ] **Step 2: Verify header renders**

Run: `cd frontend && npm run dev`. Check that the header shows the logo, nav menu, health status, and user dropdown correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppHeader.vue
git commit -m "refactor(header): use design tokens, flat styling"
```

---

## Task 18: AppDrawer — Update Token References

**Files:**
- Modify: `frontend/src/design-system/components/AppDrawer.vue`

- [ ] **Step 1: Update AppDrawer.vue styles**

The component is functional and mostly fine. Update the style to use the new token:

```vue
<style scoped>
.app-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: var(--color-bg-elevated);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/design-system/components/AppDrawer.vue
git commit -m "refactor(drawer): update to use new color tokens"
```

---

## Task 19: Sidebar Components — Update Styling

**Files:**
- Modify: `frontend/src/components/layout/AppSidebar.vue` (no changes needed — uses `.app-sidebar` class from custom.css)
- Modify: `frontend/src/components/layout/sidebars/ChatSessionsSidebar.vue`
- Modify: `frontend/src/components/layout/sidebars/ExhibitFilterSidebar.vue`
- Modify: `frontend/src/components/layout/sidebars/TourPlanSidebar.vue`
- Modify: `frontend/src/components/layout/sidebars/AdminNavSidebar.vue`

- [ ] **Step 1: Read all sidebar files**

Read each sidebar file and identify any hard-coded colors, fonts, or shadows.

- [ ] **Step 2: Replace hard-coded values with tokens**

For each sidebar file, replace:
- `#e4e7ed` or similar border colors → `var(--color-border)`
- `#fafafa` or similar backgrounds → `var(--color-bg-elevated)`
- `font-family: var(--font-family-display)` → `font-family: var(--font-family-base)`
- Any `box-shadow` → remove
- Hard-coded font sizes → `var(--font-size-*)` tokens
- Hard-coded spacing → `var(--space-*)` tokens

- [ ] **Step 3: Verify sidebars render**

Run: `cd frontend && npm run dev`. Check each sidebar type renders correctly by navigating to different routes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/sidebars/
git commit -m "refactor(sidebars): replace hard-coded values with design tokens"
```

---

## Task 20: View Components — Flatten Styling

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/views/TourView.vue`
- Modify: `frontend/src/views/CuratorView.vue`
- Modify: `frontend/src/views/ExhibitsView.vue`
- Modify: `frontend/src/views/DesignSystemView.vue`
- Modify: `frontend/src/views/NotFoundView.vue`

- [ ] **Step 1: Read all view files**

Read each view file and identify hard-coded styles, decorative elements, and dark theme references.

- [ ] **Step 2: Update HomeView.vue**

- Remove any decorative motif imports/usage
- Replace hard-coded colors with tokens
- Replace `font-family: var(--font-family-display)` with `var(--font-family-base)`
- Remove any `box-shadow` references
- Use `var(--space-fluid-*)` for page-level spacing

- [ ] **Step 3: Update TourView.vue**

- Remove `data-theme="tour-dark"` attribute setting
- Remove any dark-theme-specific class toggling
- Replace cinematic transition durations with `var(--duration-slow)`
- Replace hard-coded colors with tokens

- [ ] **Step 4: Update CuratorView.vue**

- Replace hard-coded colors, fonts, shadows with tokens
- Remove decorative motif imports/usage

- [ ] **Step 5: Update ExhibitsView.vue**

- Replace hard-coded values with tokens

- [ ] **Step 6: Update DesignSystemView.vue**

- Update to reflect the new flat design system
- Remove dark theme preview section
- Update color swatches to new palette
- Update typography samples to new clamp() sizes

- [ ] **Step 7: Update NotFoundView.vue**

- Replace hard-coded values with tokens

- [ ] **Step 8: Verify all views render**

Run: `cd frontend && npm run dev`. Navigate to each route and verify rendering.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/
git commit -m "refactor(views): flatten styling, remove dark theme, use tokens"
```

---

## Task 21: Tour Components — Remove Dark Theme

**Files:**
- Modify: All 19 files in `frontend/src/components/tour/` and `frontend/src/components/tour/workspace/`

- [ ] **Step 1: Search for dark theme references**

Run: `grep -rn "data-theme\|tour-dark\|theme.*dark" frontend/src/components/tour/`

- [ ] **Step 2: For each tour component**

- Remove any `data-theme="tour-dark"` attribute or dynamic theme toggling
- Remove `:root[data-theme='tour-dark']` CSS blocks if present in `<style>` sections
- Replace `--duration-cinematic` with `--duration-slow`
- Replace `--ease-museum` with `--ease-default`
- Replace `font-family: var(--font-family-display)` with `var(--font-family-base)`
- Replace hard-coded colors with tokens
- Remove `box-shadow` references

- [ ] **Step 3: Verify Tour flow renders**

Run: `cd frontend && npm run dev`. Navigate to `/tour` and walk through the tour flow (onboarding → opening → hall-select → workspace → report). Verify all steps render correctly with the light theme.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/tour/
git commit -m "refactor(tour): remove dark theme, flatten styling"
```

---

## Task 22: Admin Components — Flatten Styling

**Files:**
- Modify: All 7 files in `frontend/src/components/admin/`

- [ ] **Step 1: For each admin component**

- Replace hard-coded colors with tokens
- Replace hard-coded font sizes/weights with tokens
- Remove `box-shadow` references
- Replace `font-family: var(--font-family-display)` with `var(--font-family-base)`

- [ ] **Step 2: Verify admin pages render**

Run: `cd frontend && npm run dev`. Navigate to `/admin/exhibits`, `/admin/documents`, `/admin/prompts`, etc. and verify rendering.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/
git commit -m "refactor(admin): flatten styling, use design tokens"
```

---

## Task 23: Auth Components — Flatten Styling

**Files:**
- Modify: `frontend/src/components/auth/AuthModal.vue`
- Modify: `frontend/src/components/auth/LoginForm.vue`
- Modify: `frontend/src/components/auth/RegisterForm.vue`

- [ ] **Step 1: For each auth component**

- Replace hard-coded colors with tokens
- Replace hard-coded spacing with tokens
- Remove `box-shadow` references
- Replace `font-family: var(--font-family-display)` with `var(--font-family-base)`

- [ ] **Step 2: Verify auth modal renders**

Run: `cd frontend && npm run dev`. Click the login button and verify the modal, login form, and register form render correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/auth/
git commit -m "refactor(auth): flatten styling, use design tokens"
```

---

## Task 24: Chat Components — Flatten Styling

**Files:**
- Modify: `frontend/src/components/chat/ChatMainArea.vue`
- Modify: `frontend/src/components/chat/MessageItem.vue`
- Modify: `frontend/src/components/chat/SourceCard.vue`
- Modify: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: For each chat component**

- Replace hard-coded colors with tokens
- Replace hard-coded spacing with tokens
- Remove `box-shadow` references
- Replace `font-family: var(--font-family-display)` with `var(--font-family-base)`

- [ ] **Step 2: Verify chat renders**

Run: `cd frontend && npm run dev`. Navigate to `/` and send a message to verify the chat interface renders correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/ frontend/src/components/ChatPanel.vue
git commit -m "refactor(chat): flatten styling, use design tokens"
```

---

## Task 25: Remaining Components — Flatten Styling

**Files:**
- Modify: `frontend/src/components/profile/ProfileSettings.vue`
- Modify: `frontend/src/components/exhibits/ExhibitFilter.vue`
- Modify: `frontend/src/components/exhibits/ExhibitList.vue`
- Modify: `frontend/src/components/curator/ExhibitCard.vue`
- Modify: `frontend/src/components/curator/ReflectionPanel.vue`
- Modify: `frontend/src/components/curator/TourPathView.vue`
- Modify: `frontend/src/components/curator/TourPlanner.vue`
- Modify: `frontend/src/components/knowledge/DocumentList.vue`
- Modify: `frontend/src/components/knowledge/DocumentUpload.vue`
- Modify: `frontend/src/components/HealthCard.vue`
- Modify: `frontend/src/components/DocumentActions.vue`

- [ ] **Step 1: For each component**

- Replace hard-coded colors with tokens
- Replace hard-coded spacing with tokens
- Remove `box-shadow` references
- Replace `font-family: var(--font-family-display)` with `var(--font-family-base)`
- Remove motif imports and usage

- [ ] **Step 2: Verify pages render**

Run: `cd frontend && npm run dev`. Navigate to `/exhibits`, `/curator`, `/profile` and verify rendering.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/
git commit -m "refactor(components): flatten remaining components, use tokens"
```

---

## Task 26: Cleanup — Remove Unused Motif Imports

**Files:**
- Various files across `frontend/src/`

- [ ] **Step 1: Search for motif imports**

Run: `grep -rn "from.*motifs" frontend/src/ --include="*.vue" --include="*.js"`

Identify any remaining motif imports that are no longer used.

- [ ] **Step 2: Remove unused imports**

For each file that imports motifs no longer used in its template, remove the import line.

- [ ] **Step 3: Search for `--font-family-display` and `--font-family-serif` references**

Run: `grep -rn "font-family-display\|font-family-serif" frontend/src/ --include="*.vue" --include="*.css"`

Replace any remaining references with `--font-family-base`.

- [ ] **Step 4: Search for remaining hard-coded colors**

Run: `grep -rn "#f5eedc\|#fdfaf2\|#efe5cc\|#fbf5e6\|#d9c9a8\|#c89d5a" frontend/src/ --include="*.vue"`

Replace any remaining old color values with the new token references.

- [ ] **Step 5: Search for `--color-gold-line` references**

Run: `grep -rn "gold-line" frontend/src/ --include="*.vue" --include="*.css"`

Replace with `--color-gold` (the token was renamed).

- [ ] **Step 6: Verify full app renders**

Run: `cd frontend && npm run dev`. Navigate through all routes and verify nothing is broken.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "refactor(cleanup): remove unused motif imports, fix remaining token references"
```

---

## Task 27: Final Verification

- [ ] **Step 1: Run the dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Test all routes**

Navigate to every route and verify:
- `/` — Home page with chat
- `/tour` — Tour flow (all 5 steps)
- `/curator` — Tour planner
- `/exhibits` — Exhibit browser
- `/profile` — Profile settings
- `/admin/exhibits` — Admin exhibits
- `/admin/documents` — Admin documents
- `/admin/prompts` — Admin prompts
- `/admin/halls` — Admin halls
- `/admin/tour-paths` — Admin tour paths
- `/admin/llm-traces` — Admin LLM traces
- `/admin/tts-personas` — Admin TTS personas
- `/design-system` — Design system preview

- [ ] **Step 3: Test responsive behavior**

- Resize browser to mobile width (375px) — sidebar should collapse to drawer
- Resize to desktop (1920px) — sidebar visible, full layout
- Check that text scales at different widths (verify `clamp()` is working)

- [ ] **Step 4: Run linting**

```bash
cd frontend && npm run lint
```

Fix any linting errors.

- [ ] **Step 5: Run build**

```bash
cd frontend && npm run build
```

Verify the production build succeeds.

- [ ] **Step 6: Commit any fixes**

```bash
git add frontend/
git commit -m "fix: address lint errors from flat design refactor"
```
