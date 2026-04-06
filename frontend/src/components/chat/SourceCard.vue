<script setup>
import { ref } from 'vue'
import { Document } from '@element-plus/icons-vue'

defineProps({
  source: {
    type: Object,
    required: true,
  },
})

const expanded = ref(false)
</script>

<template>
  <el-card shadow="hover" style="margin-top: 8px; font-size: 13px;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>
          <el-icon><Document /></el-icon>
          {{ source.source || '未知来源' }}
        </span>
        <el-tag size="small" type="info" :title="`原始分数: ${(source.score || 0).toFixed(4)}`">
          相似度: {{ ((source.score || 0) * 100).toFixed(1) }}%
        </el-tag>
      </div>
    </template>
    <div :style="{ maxHeight: expanded ? 'none' : '60px', overflow: 'hidden' }">
      {{ source.content || source.text || '' }}
    </div>
    <el-button link @click="expanded = !expanded" style="margin-top: 8px;">
      {{ expanded ? '收起' : '展开' }}
    </el-button>
  </el-card>
</template>
