<script setup>
import { ChatLineRound } from '@element-plus/icons-vue'

defineProps({
  questions: {
    type: Array,
    default: () => []
  }
})
</script>

<template>
  <el-card class="reflection-panel" v-if="questions.length">
    <template #header>
      <div class="header">
        <el-icon><ChatLineRound /></el-icon>
        <span>思考引导</span>
      </div>
    </template>

    <ul class="questions">
      <li v-for="(question, index) in questions" :key="index">
        {{ question }}
      </li>
    </ul>
  </el-card>
</template>

<style scoped>
.reflection-panel {
  margin-top: 16px;
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.questions {
  margin: 0;
  padding-left: 20px;
}

.questions li {
  margin-bottom: 12px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
}
</style>
