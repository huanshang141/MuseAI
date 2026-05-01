<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function startTour() {
  router.push('/tour')
}
</script>

<template>
  <section class="sidebar-section tour-plan-sidebar">
    <header class="sidebar-header">
      <h3>导览助手</h3>
      <p>根据你的兴趣和时长快速规划路线。</p>
    </header>

    <ol class="tips">
      <li>先选择可用参观时长</li>
      <li>勾选感兴趣的主题</li>
      <li>点击地图标记查看细节</li>
    </ol>

    <el-button type="primary" @click="startTour">进入 AI 导览模式</el-button>
  </section>
</template>

<style scoped>
.sidebar-section {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sidebar-header h3 {
  margin: 0;
  font-size: var(--font-size-h4);
}

.sidebar-header p {
  margin: var(--space-2) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-sm);
  line-height: 1.6;
}

.tips {
  margin: 0;
  padding-left: var(--space-4);
  color: var(--color-text-secondary);
  font-size: var(--font-size-body-sm);
  display: grid;
  gap: var(--space-2);
}
</style>
