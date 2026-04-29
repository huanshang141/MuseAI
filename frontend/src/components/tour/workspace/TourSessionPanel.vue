<script setup>
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useTour } from '../../../composables/useTour.js'
import { useTourWorkbench } from '../../../composables/useTourWorkbench.js'

const { chatMessages, streamingContent, loading, sendTourMessage, currentExhibit, suggestedActions } = useTour()
const { chatDraft, buildStyledPrompt, uiPreferences, activeTab } = useTourWorkbench()

const messagesArea = ref(null)

function scrollToBottom() {
  if (!uiPreferences.value.autoScroll) return
  const el = messagesArea.value
  if (el) el.scrollTop = el.scrollHeight
}

watch([chatMessages, streamingContent], () => {
  nextTick(scrollToBottom)
}, { deep: true })

watch(activeTab, (newTab, oldTab) => {
  if (oldTab === 'session' && !uiPreferences.value.rememberDraft) {
    chatDraft.value = ''
  }
})

async function sendMessage() {
  if (!chatDraft.value.trim() || loading.value.chat) return
  const rawInput = chatDraft.value.trim()
  const styledInput = buildStyledPrompt(rawInput)
  chatDraft.value = ''
  chatMessages.value.push({ role: 'user', content: rawInput })
  await sendTourMessage(styledInput, true)
}

onMounted(scrollToBottom)
</script>

<template>
  <div class="tour-session-panel">
    <div v-if="currentExhibit" class="session-exhibit-bar">
      <span class="exhibit-name">{{ currentExhibit.name }}</span>
    </div>
    <div ref="messagesArea" class="messages-area">
      <div v-for="(msg, i) in chatMessages" :key="msg.role + '-' + i" class="message" :class="msg.role">
        <span class="msg-content">{{ msg.content }}</span>
      </div>
      <div v-if="loading.chat && streamingContent" class="message assistant streaming-content">
        <span class="msg-content">{{ streamingContent }}<span class="cursor">|</span></span>
      </div>
      <div v-if="loading.chat && !streamingContent" class="message assistant loading-hint">
        <span class="msg-content">正在思考<span class="dots">...</span></span>
      </div>
    </div>
    <div v-if="suggestedActions && !loading.chat && uiPreferences.showQuickPrompts" class="quick-prompts">
      <div v-if="suggestedActions.deep_dive_prompt" class="quick-prompt-chip" @click="chatDraft = suggestedActions.deep_dive_prompt">
        💡 {{ suggestedActions.deep_dive_prompt }}
      </div>
    </div>
    <div class="input-area">
      <el-input v-model="chatDraft" placeholder="向导览员提问..." @keyup.enter="sendMessage" :disabled="loading.chat">
        <template #append><el-button @click="sendMessage" :loading="loading.chat">发送</el-button></template>
      </el-input>
    </div>
  </div>
</template>

<style scoped>
.tour-session-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.session-exhibit-bar {
  padding: 8px 16px;
  border-bottom: 1px solid var(--color-border, #d9c9a8);
  background: var(--color-bg-elevated, #fdfaf2);
}

.exhibit-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-accent, #a94c2c);
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--color-bg-base, #f5eedc);
}

.message {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message.user {
  align-self: flex-end;
  background: var(--color-accent-muted, rgba(212, 165, 116, 0.2));
  color: var(--color-text-primary, #2a2420);
}

.message.assistant {
  align-self: flex-start;
  background: var(--color-surface-card, #fbf5e6);
  color: var(--color-text-primary, #2a2420);
}

.loading-hint {
  opacity: 0.6;
}

.dots {
  animation: dots-pulse 1.2s infinite;
}

@keyframes dots-pulse {
  0%, 20% { opacity: 0.2; }
  40% { opacity: 0.6; }
  60%, 100% { opacity: 1; }
}

.cursor {
  animation: blink 0.8s infinite;
  color: var(--color-accent, #a94c2c);
}

@keyframes blink {
  0%, 50% { opacity: 1 }
  51%, 100% { opacity: 0 }
}

.quick-prompts {
  padding: 8px 16px;
}

.quick-prompt-chip {
  padding: 8px 14px;
  background: var(--color-accent-muted, rgba(212, 165, 116, 0.15));
  border: 1px solid var(--color-accent-soft, #c47a52);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-accent, #a94c2c);
  transition: background 0.15s;
}

.quick-prompt-chip:hover {
  background: var(--color-accent-muted, rgba(212, 165, 116, 0.25));
}

.input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border, #d9c9a8);
  background: var(--color-bg-elevated, #fdfaf2);
}
</style>
