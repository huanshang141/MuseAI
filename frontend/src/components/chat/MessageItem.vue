<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
  },
})

function formatTime(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div :style="{
    display: 'flex',
    justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
    marginBottom: '16px',
  }">
    <div :style="{
      maxWidth: '80%',
      padding: '12px 16px',
      borderRadius: '12px',
      background: message.role === 'user' ? 'var(--el-color-primary)' : 'var(--el-fill-color-light)',
      color: message.role === 'user' ? '#fff' : 'var(--el-text-color-primary)',
    }">
      <div style="white-space: pre-wrap; word-break: break-word;">
        {{ message.content }}
      </div>
      <div v-if="message.trace_id" style="font-size: 11px; margin-top: 8px; opacity: 0.7;">
        Trace: {{ message.trace_id }}
      </div>
      <div style="font-size: 11px; margin-top: 6px; opacity: 0.6;">
        {{ formatTime(message.created_at) }}
      </div>
    </div>
  </div>
</template>
