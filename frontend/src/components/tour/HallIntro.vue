<script setup>
import { ref, onMounted } from 'vue'
import { useTour } from '../../composables/useTour.js'

const props = defineProps({ hall: String, hallName: String })
const emit = defineEmits(['done'])

const { tourSession, sendTourMessage, streamingContent, chatMessages, loading } = useTour()

const hallIntroPrompts = {
  A: `请以考古队长的身份，为游客介绍${props.hallName}。简要说明这个展厅的主题和重点观察方向，3-4句话即可。`,
  B: `请以半坡原住民的身份，为远道而来的朋友介绍${props.hallName}。用第一人称，2-3句话即可。`,
  C: `请以历史老师的身份，为同学们介绍${props.hallName}。抛出一个引人思考的问题，2-3句话即可。`,
}

onMounted(async () => {
  await sendTourMessage(hallIntroPrompts[tourSession.value?.persona || 'A'])
})

function continueTour() { emit('done') }
</script>

<template>
  <div class="hall-intro">
    <h2 class="hall-title">{{ hallName }}</h2>
    <div class="intro-content">
      <template v-if="chatMessages.length > 0">
        <p v-for="msg in chatMessages.filter(m => m.role === 'assistant')" :key="msg.content" class="intro-text">{{ msg.content }}</p>
      </template>
      <p v-if="loading.chat" class="intro-text typing">{{ streamingContent }}<span class="cursor">|</span></p>
    </div>
    <el-button v-if="!loading.chat && chatMessages.length > 0" type="primary" @click="continueTour">开始参观 →</el-button>
  </div>
</template>

<style scoped>
.hall-intro { padding: 40px 24px; text-align: center; max-width: 640px; margin: 0 auto; }
.hall-title { font-size: 24px; color: var(--color-accent); margin-bottom: 24px; }
.intro-content { margin-bottom: 32px; }
.intro-text { font-size: 16px; line-height: 2; color: var(--color-text-primary); text-align: left; white-space: pre-wrap; }
.cursor { animation: blink 0.8s infinite; color: var(--color-accent); }
@keyframes blink { 0%,50%{opacity:1} 51%,100%{opacity:0} }
</style>
