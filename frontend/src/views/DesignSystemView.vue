<script setup>
import { ref } from 'vue'
import {
  MuseumButton,
  MuseumCard,
  MuseumDialog,
  EmptyState,
  SectionDivider,
} from '../design-system/components/index.js'
import {
  FishFaceSymbol,
  FishSwim,
  RopePattern,
  NetPattern,
  TrianglePattern,
  PointedJar,
  FishFaceBasin,
  ClayPot,
} from '../design-system/motifs/index.js'
import { BREAKPOINTS } from '../design-system/tokens/breakpoints.js'

const colorTokens = [
  { name: '--color-accent', value: 'var(--color-accent)' },
  { name: '--color-bg-base', value: 'var(--color-bg-base)' },
  { name: '--color-bg-elevated', value: 'var(--color-bg-elevated)' },
  { name: '--color-jade', value: 'var(--color-jade)' },
  { name: '--color-gold-line', value: 'var(--color-gold-line)' },
  { name: '--color-text-primary', value: 'var(--color-text-primary)' },
]

const showDialog = ref(false)
</script>

<template>
  <div class="design-system-view">
    <header class="hero">
      <FishFaceSymbol :size="56" class="hero-mark" aria-label="MuseAI motif" />
      <div>
        <h1>MuseAI Design System</h1>
        <p>半坡陶土风设计令牌、母题与组件预览</p>
      </div>
    </header>

    <section>
      <h2>Colors</h2>
      <div class="swatches">
        <div v-for="token in colorTokens" :key="token.name" class="swatch">
          <div class="chip" :style="{ background: token.value }" />
          <span>{{ token.name }}</span>
        </div>
      </div>
    </section>

    <section>
      <h2>Typography</h2>
      <p class="display">半坡遗址 Banpo Museum 2026</p>
      <p class="body">以陶土与纹样构建现代博物馆导览体验。</p>
    </section>

    <section>
      <h2>Breakpoints</h2>
      <p>xs {{ BREAKPOINTS.xs }} / sm {{ BREAKPOINTS.sm }} / md {{ BREAKPOINTS.md }} / lg {{ BREAKPOINTS.lg }} / xl {{ BREAKPOINTS.xl }}</p>
    </section>

    <section>
      <h2>Motifs</h2>
      <div class="motifs">
        <FishFaceSymbol :size="56" />
        <FishSwim :size="56" />
        <RopePattern :size="120" />
        <NetPattern :size="64" />
        <TrianglePattern :size="100" />
        <PointedJar :size="56" />
        <FishFaceBasin :size="56" />
        <ClayPot :size="56" />
      </div>
    </section>

    <section>
      <h2>Components</h2>
      <MuseumCard title="半坡彩陶盆" subtitle="新石器时代 · 人面鱼纹" :accent="true" motif="basin">
        <p>MuseumCard、MuseumButton、SectionDivider、EmptyState 示例。</p>
        <div class="buttons">
          <MuseumButton variant="primary">Primary</MuseumButton>
          <MuseumButton variant="secondary">Secondary</MuseumButton>
          <MuseumButton variant="ghost">Ghost</MuseumButton>
          <MuseumButton variant="text" @click="showDialog = true">Open Dialog</MuseumButton>
        </div>
      </MuseumCard>
      <SectionDivider :ornament="true" />
      <EmptyState icon="jar" title="示例空状态" description="用于替换系统默认空状态" />
      <MuseumDialog :visible="showDialog" title="Dialog Example" @update:visible="showDialog = $event">
        <p>这是 MuseumDialog 的预览内容。</p>
        <template #footer>
          <MuseumButton variant="secondary" @click="showDialog = false">Close</MuseumButton>
        </template>
      </MuseumDialog>
    </section>
  </div>
</template>

<style scoped>
.design-system-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  padding: var(--space-6);
  color: var(--color-text-primary);
}

.hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.hero h1 {
  margin: 0;
  font-family: var(--font-family-display);
  font-size: var(--font-size-h1);
}

.hero p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-secondary);
}

.hero-mark {
  color: var(--color-accent);
}

section h2 {
  margin: 0 0 var(--space-3);
  font-family: var(--font-family-display);
  font-size: var(--font-size-h3);
}

.swatches {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.swatch {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-elevated);
}

.chip {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--color-border-strong);
}

.display {
  margin: 0;
  font-size: var(--font-size-display);
  line-height: var(--line-height-tight);
}

.body {
  margin: var(--space-3) 0 0;
  font-size: var(--font-size-body);
  line-height: var(--line-height-normal);
}

.motifs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  color: var(--color-accent);
}

.buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}
</style>
