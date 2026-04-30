<script setup>
import { ref } from 'vue'
import { useTour } from '../../composables/useTour.js'
import { useTourWorkbench } from '../../composables/useTourWorkbench.js'
import { useTTSPlayer } from '../../composables/useTTSPlayer.js'
import { api } from '../../api/index.js'

const props = defineProps({ exhibit: Object })
const emit = defineEmits(['deep-dive'])

const { sendTourMessage, streamingContent, chatMessages, loading, suggestedActions, tourSession } = useTour()
const { ttsPreferences } = useTourWorkbench()
const { feedChunk, stop: stopTTS } = useTTSPlayer()
const inputMessage = ref('')
const manualTtsPlaying = ref(false)

async function sendMessage() {
  if (!inputMessage.value.trim() || loading.value.chat) return
  const msg = inputMessage.value.trim()
  inputMessage.value = ''
  await sendTourMessage(msg)
}

async function playMessageTTS(text) {
  if (!text) return
  if (manualTtsPlaying.value) {
    stopTTS()
    manualTtsPlaying.value = false
    return
  }
  manualTtsPlaying.value = true
  try {
    const persona = tourSession.value?.persona || 'A'
    const result = await api.tts.synthesize(text, ttsPreferences.value.voice, null, persona)
    if (result.ok && result.data?.audio) {
      stopTTS()
      feedChunk(result.data.audio)
      manualTtsPlaying.value = false
    } else {
      manualTtsPlaying.value = false
    }
  } catch (err) {
    console.error('TTS playback error:', err)
    manualTtsPlaying.value = false
  }
}

function handleDeepDive() { emit('deep-dive') }
</script>

<template>
  <div class="exhibit-chat">
    <div v-if="exhibit" class="exhibit-header">
      <h3 class="exhibit-name">{{ exhibit.name }}</h3>
      <p v-if="exhibit.description" class="exhibit-desc">{{ exhibit.description }}</p>
    </div>
    <div class="messages">
      <div v-for="(msg, i) in chatMessages" :key="i" class="message" :class="msg.role">
        <span class="msg-content">{{ msg.content }}</span>
        <button
          v-if="msg.role === 'assistant' && ttsPreferences.enabled"
          class="speaker-btn"
          title="语音播放"
          :disabled="manualTtsPlaying"
          @click="playMessageTTS(msg.content)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
        </button>
      </div>
      <div v-if="loading.chat && streamingContent" class="message assistant">
        <span class="msg-content">{{ streamingContent }}<span class="cursor">|</span></span>
      </div>
    </div>
    <div v-if="suggestedActions && !loading.chat" class="suggestions">
      <div v-if="suggestedActions.deep_dive_prompt" class="suggestion-card" @click="handleDeepDive">💡 {{ suggestedActions.deep_dive_prompt }}</div>
    </div>
    <div class="input-area">
      <el-input v-model="inputMessage" placeholder="向导览员提问..." @keyup.enter="sendMessage" :disabled="loading.chat">
        <template #append><el-button @click="sendMessage" :loading="loading.chat">发送</el-button></template>
      </el-input>
    </div>
  </div>
</template>

<style scoped>
.exhibit-chat { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.exhibit-header { padding: 16px 24px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.exhibit-name { font-size: 18px; color: #f0e6d3; margin-bottom: 4px; }
.exhibit-desc { font-size: 13px; color: rgba(255,255,255,0.5); line-height: 1.6; }
.messages { flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 12px; }
.message { max-width: 80%; padding: 12px 16px; border-radius: 12px; font-size: 15px; line-height: 1.7; white-space: pre-wrap; }
.message.user { align-self: flex-end; background: rgba(212,165,116,0.2); color: #f0e6d3; }
.message.assistant { align-self: flex-start; background: rgba(255,255,255,0.06); color: #e0e0e0; position: relative; }
.speaker-btn { position: absolute; bottom: 4px; right: 4px; background: none; border: none; cursor: pointer; color: rgba(255,255,255,0.3); padding: 4px; border-radius: 4px; display: flex; align-items: center; transition: color 0.2s, background 0.2s; }
.speaker-btn:hover { color: #d4a574; background: rgba(212,165,116,0.1); }
.speaker-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.cursor { animation: blink 0.8s infinite; color: #d4a574; }
@keyframes blink { 0%,50%{opacity:1} 51%,100%{opacity:0} }
.suggestions { padding: 8px 24px; }
.suggestion-card { padding: 12px 16px; background: rgba(212,165,116,0.1); border: 1px solid rgba(212,165,116,0.2); border-radius: 8px; cursor: pointer; font-size: 14px; color: #d4a574; transition: background 0.2s; }
.suggestion-card:hover { background: rgba(212,165,116,0.2); }
.input-area { padding: 12px 24px; border-top: 1px solid rgba(255,255,255,0.08); }
</style>
