<script setup>
import { useRouter } from 'vue-router'
import { MuseumPage } from '../design-system/components/index.js'
import ChatMainArea from '../components/chat/ChatMainArea.vue'

const router = useRouter()

function startTour() {
  router.push('/tour')
}
</script>

<template>
  <MuseumPage class="home-view">
    <div class="home-hero">
      <h1>与半坡对话</h1>
      <p>六千年的陶土之下，每一个疑问都值得追问。</p>
      <el-button type="warning" @click="startTour">开始导览</el-button>
    </div>

    <ChatMainArea />
  </MuseumPage>
</template>

<style scoped>
.home-view {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.home-view :deep(.museum-page-content) {
  flex: 1;
  min-height: 0;
}

.home-view :deep(.museum-page-main) {
  min-height: 0;
}

.home-hero {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.home-hero h1 {
  margin: 0;
  font-size: clamp(24px, 3vw, 32px);
  font-family: var(--font-family-base);
}

.home-hero p {
  margin: 0;
  color: var(--color-text-secondary);
  max-width: 560px;
  line-height: 1.6;
}

@media (min-width: 768px) {
  .home-view :deep(.museum-page-main) {
    min-height: calc(100vh - 250px);
  }
}

@media (max-width: 767px) {
  .home-hero {
    gap: 8px;
  }
}
</style>
