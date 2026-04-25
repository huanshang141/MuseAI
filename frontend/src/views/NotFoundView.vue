<script setup>
import { useRouter } from 'vue-router'
import { EmptyState, MuseumButton, MuseumPage } from '../design-system/components/index.js'

const router = useRouter()

function goHome() {
  router.push('/')
}
</script>

<template>
  <MuseumPage class="not-found-view">
    <template #hero>
      <h1>页面走失了</h1>
      <p>你访问的路径不存在，可能已经被迁移或拼写有误。</p>
    </template>

    <EmptyState icon="fish" title="404 · 未找到页面" description="可以返回首页继续浏览半坡展览与导览内容。">
      <MuseumButton variant="primary" @click="goHome">返回首页</MuseumButton>
    </EmptyState>
  </MuseumPage>
</template>

<style scoped>
.not-found-view {
  max-width: 760px;
  margin: 0 auto;
  padding-top: 24px;
}

h1 {
  margin: 0;
  font-size: clamp(24px, 3vw, 32px);
  font-family: var(--font-family-display);
}

p {
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.6;
}
</style>
