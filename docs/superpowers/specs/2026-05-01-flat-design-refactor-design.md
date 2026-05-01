# Flat Design Refactor — Design Spec

## Overview

Refactor the entire MuseAI frontend from a "museum terracotta" aesthetic (warm parchment, serif fonts, shadows, decorative motifs) to a flat design system. The goal is a clean, information-focused interface that works across mobile, desktop 1080p, and desktop 4K resolutions.

## Scope

**All pages and components** — public (Home, Tour, Exhibits, Curator), admin, auth, profile, layout shell. No exceptions.

## Design Principles

- **Color blocks over shadows** — hierarchy via color depth, not elevation
- **Typography over decoration** — font weight, size, and color for structure
- **Flat surfaces** — pure color backgrounds, 1px solid borders, no gradients
- **Minimal motion** — short transitions (100-250ms), color-change feedback only
- **Responsive fluidity** — `clamp()` for typography and spacing, max-width containers for large screens

## 1. Color System

### Light Theme (unified — no dark theme)

Keep the museum accent palette, flatten the treatment:

| Token | Value | Usage |
|---|---|---|
| `--color-bg-base` | `#ffffff` | Page background |
| `--color-bg-elevated` | `#f8f6f1` | Sidebar, secondary surfaces |
| `--color-bg-subtle` | `#f0ece3` | Table headers, hover states |
| `--color-surface-card` | `#ffffff` | Cards (same as base — flat) |
| `--color-border` | `#e8e2d6` | All borders |
| `--color-divider` | `#e8e2d6` | Dividers (flat, no gold gradient) |
| `--color-text-primary` | `#1a1816` | Headings |
| `--color-text-secondary` | `#3a3632` | Body text |
| `--color-text-muted` | `#6a6460` | Secondary/caption text |
| `--color-text-faint` | `#9a9490` | Placeholders, hints |
| `--color-accent` | `#a94c2c` | Primary actions, active states |
| `--color-accent-hover` | `#8f3f23` | Hover (darken 10%) |
| `--color-accent-soft` | `#c47a52` | Accent variant |
| `--color-jade` | `#5a7a6b` | Success |
| `--color-gold` | `#c89d5a` | Warning |
| `--color-danger` | `#8b2f1f` | Error, destructive actions |

**Remove:** `data-theme="tour-dark"` — the Tour flow uses the same light theme.

## 2. Typography

### Font Family

Switch to sans-serif primary:

```css
--font-family-base: 'Source Han Sans CN', 'PingFang SC', 'Microsoft YaHei', sans-serif;
--font-family-mono: 'JetBrains Mono', 'Fira Code', monospace;
```

Remove `--font-family-serif` from the base stack. The display/body distinction (serif vs sans) is removed.

### Fluid Font Sizes (clamp)

All typography tokens use `clamp(min, preferred, max)` for viewport-responsive scaling:

| Token | clamp() | At 375px | At 1920px | At 3840px |
|---|---|---|---|---|
| `--font-size-display` | `clamp(2rem, 3.5vw + 0.5rem, 4.5rem)` | 32px | 48px | 72px |
| `--font-size-h1` | `clamp(1.5rem, 2.5vw + 0.25rem, 3.25rem)` | 24px | 32px | 52px |
| `--font-size-h2` | `clamp(1.25rem, 1.8vw + 0.25rem, 2.5rem)` | 20px | 26px | 40px |
| `--font-size-h3` | `clamp(1.125rem, 1.2vw + 0.25rem, 1.875rem)` | 18px | 22px | 30px |
| `--font-size-h4` | `clamp(1rem, 1vw + 0.25rem, 1.5rem)` | 16px | 18px | 24px |
| `--font-size-body` | `clamp(0.875rem, 0.5vw + 0.625rem, 1.125rem)` | 14px | 15px | 18px |
| `--font-size-body-sm` | `clamp(0.75rem, 0.3vw + 0.5625rem, 0.9375rem)` | 12px | 13px | 15px |
| `--font-size-caption` | `clamp(0.6875rem, 0.2vw + 0.5625rem, 0.875rem)` | 11px | 12px | 14px |
| `--font-size-label` | `clamp(0.625rem, 0.15vw + 0.5rem, 0.8125rem)` | 10px | 11px | 13px |

Remove the existing `@media (max-width: 767px)` typography overrides — `clamp()` handles the mobile floor.

### Font Weights

| Token | Value | Usage |
|---|---|---|
| `--font-weight-regular` | 400 | Body text |
| `--font-weight-medium` | 500 | Buttons, labels |
| `--font-weight-semibold` | 600 | Card titles, section headings |
| `--font-weight-bold` | 700 | Page titles, display |

## 3. Spacing

### Static Spacing (component-level — fixed for touch targets)

Keep existing `--space-*` tokens as-is for buttons, inputs, icons, and any element requiring consistent sizing.

### Fluid Spacing (page-level — scales with viewport)

Add new fluid tokens:

| Token | Value | Usage |
|---|---|---|
| `--space-fluid-xs` | `clamp(0.5rem, 1vw, 1rem)` | Tight gaps |
| `--space-fluid-sm` | `clamp(0.75rem, 1.5vw, 1.5rem)` | Section padding |
| `--space-fluid-md` | `clamp(1rem, 2vw, 2.5rem)` | Card gaps, page padding |
| `--space-fluid-lg` | `clamp(1.5rem, 3vw, 4rem)` | Major section gaps |
| `--space-fluid-xl` | `clamp(2rem, 4vw, 6rem)` | Hero/landing spacing |

## 4. Layout

### Max-Width Container Tokens

| Token | Value | Usage |
|---|---|---|
| `--content-width-sm` | `640px` | Text-heavy content (chat, articles) |
| `--content-width-md` | `840px` | Forms, settings |
| `--content-width-lg` | `1200px` | Dashboards, grids |
| `--content-width-full` | `1440px` | Page max-width |

### Page Shell

The root layout (`App.vue`) wraps content in a max-width container:

```css
.app-shell {
  max-width: min(var(--content-width-full), 90vw);
  margin: 0 auto;
}
```

At 4K, the content is capped at 1440px and centered, with breathing room on both sides. Typography and spacing automatically scale up via `clamp()` so nothing looks tiny.

### Grid Pattern

Use `auto-fit` with `minmax` for responsive grids:

```css
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
  gap: var(--space-fluid-md);
}
```

## 5. Border Radius

Simplify — flat design uses minimal rounding:

| Token | Value | Usage |
|---|---|---|
| `--radius-none` | `0` | — |
| `--radius-sm` | `2px` | Buttons, inputs, cards, tags (default) |
| `--radius-md` | `4px` | Modals, larger containers |
| `--radius-pill` | `999px` | Pills, status indicators |

Remove `--radius-lg` and `--radius-xl`. The default for most elements is `2px`.

## 6. Shadows

Remove all shadows. Set all shadow tokens to `none`:

```css
--shadow-sm: none;
--shadow-md: none;
--shadow-lg: none;
--shadow-focus: 0 0 0 2px rgba(169, 76, 44, 0.2); /* keep focus ring for accessibility */
```

Hierarchy is expressed through color (background depth) and borders, not elevation.

## 7. Motion

Shorten all durations — flat design favors snappy, minimal transitions:

| Token | Value | Usage |
|---|---|---|
| `--duration-fast` | `100ms` | Hover feedback |
| `--duration-normal` | `150ms` | State transitions |
| `--duration-slow` | `250ms` | Page transitions, modals |

**Remove:** `--duration-cinematic` (1200ms). No cinematic animations in flat design.

Keep `--ease-default: cubic-bezier(0.4, 0, 0.2, 1)` — it works for flat transitions.

## 8. Element Plus Theme Overrides

Update `element-theme.css` to map the new tokens onto `--el-*` variables:

- `--el-color-primary` → `var(--color-accent)`
- `--el-bg-color` → `var(--color-bg-base)`
- `--el-bg-color-page` → `var(--color-bg-base)`
- `--el-fill-color-blank` → `var(--color-bg-base)`
- `--el-fill-color-light` → `var(--color-bg-elevated)`
- `--el-border-color` → `var(--color-border)`
- `--el-border-radius-base` → `var(--radius-sm)` (2px)
- `--el-font-family` → `var(--font-family-base)`
- Remove all `--el-box-shadow-*` overrides (set to none)

## 9. Component Changes

### MuseumButton

Remove variant styling complexity. Keep 3 variants:
- **Primary:** `background: var(--color-accent)`, `color: #fff`, `border-radius: 2px`
- **Secondary:** `background: transparent`, `border: 1px solid var(--color-border)`, `color: var(--color-accent)`
- **Text:** `background: transparent`, `color: var(--color-accent)`, no border

Remove: ghost variant, accent bar decorations, motif integrations.

### MuseumCard

Remove: accent bar, motif decorations, decorative corner elements.

Simplify to: white background, 1px border, 2px radius, padding. Title in semibold, subtitle in muted color.

### MuseumDialog

Remove: themed header decoration, custom close button styling.

Simplify to: white panel, 1px border, 4px radius. Standard dialog header/body/footer.

### MuseumInput

Remove: custom focus glow, themed border animations.

Simplify to: 1px border, 2px radius, focus = accent border color only.

### MuseumPage

Remove: hero decoration, motif backgrounds, gold divider.

Simplify to: breadcrumb + title + content. Use fluid spacing for padding.

### SectionDivider

**Remove entirely.** Replace with a simple `1px solid var(--color-divider)` line or remove dividers where not needed.

### EmptyState

Remove: artifact motif icons.

Simplify to: centered text + simple icon (from Element Plus icons).

### AppDrawer

Keep as-is (functional wrapper). Remove any themed decorations.

## 10. Decorative Elements

### Motifs to Remove

Remove all motif SVG components from UI usage:
- `RopePattern`, `NetPattern`, `TrianglePattern` — pattern decorations
- `PointedJar`, `FishFaceBasin`, `ClayPot` — artifact illustrations
- `FishSwim` — decorative fish animation

These components can remain in the codebase (unused) or be deleted. They should not appear in any UI.

### Motif to Keep

- `FishFaceSymbol` — keep as the logo mark only, used in `AppHeader`. Simplify its usage (no decorative contexts).

## 11. Tour Flow

Remove the separate dark theme entirely:
- Remove `data-theme="tour-dark"` from `colors.css`
- Remove all `:root[data-theme='tour-dark']` CSS rules
- Tour components use the same light theme as the rest of the app
- Replace cinematic transitions (1200ms) with standard `--duration-slow` (250ms)

## 12. Responsive Behavior

### Breakpoints (keep existing)

| Token | Value | Behavior |
|---|---|---|
| `--bp-xs` | `0px` | Mobile portrait |
| `--bp-sm` | `640px` | Mobile landscape |
| `--bp-md` | `768px` | Tablet — sidebar collapses to drawer |
| `--bp-lg` | `1024px` | Desktop — sidebar visible |
| `--bp-xl` | `1280px` | Large desktop |

### Media Query Usage

- `@media (max-width: 767px)` — sidebar → drawer, nav menu hidden, padding reduced
- `@media (min-width: 1024px)` — sidebar visible, full layout

### Container Query Candidates

For future improvement — components that may appear in different contexts:
- Exhibit cards (grid vs sidebar vs modal)
- Chat panels (main area vs embedded)

## Files to Modify

### Token Files (core changes)
1. `design-system/tokens/colors.css` — new flat palette, remove dark theme
2. `design-system/tokens/typography.css` — sans-serif, clamp() sizes, remove media query block
3. `design-system/tokens/spacing.css` — add fluid spacing tokens
4. `design-system/tokens/radii.css` — simplify to 4 values
5. `design-system/tokens/shadows.css` — all none except focus ring
6. `design-system/tokens/motion.css` — shorten durations, remove cinematic
7. `design-system/tokens/breakpoints.css` — add container width tokens

### Theme File
8. `design-system/element-theme.css` — remap to new tokens

### Design System Components
9. `design-system/components/MuseumButton.vue` — simplify variants
10. `design-system/components/MuseumCard.vue` — remove decorations
11. `design-system/components/MuseumDialog.vue` — simplify
12. `design-system/components/MuseumInput.vue` — simplify
13. `design-system/components/MuseumPage.vue` — remove hero/decorations
14. `design-system/components/SectionDivider.vue` — remove or simplify to plain line
15. `design-system/components/EmptyState.vue` — remove motifs

### Global Styles
16. `styles/custom.css` — update layout styles, add max-width container
17. `App.vue` — add app-shell max-width wrapper

### Layout Components
18. `components/layout/AppHeader.vue` — flat styling, remove decorations
19. `components/layout/AppSidebar.vue` — flat styling

### View Components
20. `views/HomeView.vue` — flat hero, remove decorations
21. `views/TourView.vue` — remove dark theme, flatten
22. `views/CuratorView.vue` — flatten
23. `views/ExhibitsView.vue` — flatten
24. `views/DesignSystemView.vue` — update to reflect new system

### Tour Components (remove dark theme references)
25. All 19 tour components — remove `data-theme` references, flatten styling

### Admin Components
26. All 7 admin components — flatten styling

### Other Components
27. `components/auth/AuthModal.vue` — flatten
28. `components/auth/LoginForm.vue` — flatten
29. `components/auth/RegisterForm.vue` — flatten
30. `components/chat/ChatMainArea.vue` — flatten
31. `components/chat/MessageItem.vue` — flatten
32. `components/chat/SourceCard.vue` — flatten
33. `components/profile/ProfileSettings.vue` — flatten

## Implementation Order

1. **Token files** (colors, typography, spacing, radii, shadows, motion, breakpoints) — the foundation
2. **Element Plus theme overrides** — cascades to all Element Plus components
3. **Global styles + App.vue layout** — max-width container
4. **Design system components** (MuseumButton, MuseumCard, etc.) — reusable primitives
5. **Layout components** (AppHeader, AppSidebar) — navigation shell
6. **View components** — page-level layouts
7. **Feature components** — admin, chat, tour, curator, exhibits, auth, profile
8. **Cleanup** — remove unused motif imports, dark theme references

## What NOT to Change

- All business logic, composables, API calls, routing
- Element Plus component usage patterns (el-button, el-dialog, etc.)
- Responsive breakpoint behavior (sidebar collapse logic)
- Component structure and props
- Test files (update only if they assert specific style values)
