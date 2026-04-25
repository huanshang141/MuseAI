<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useChat } from '../../composables/useChat.js'
import MessageItem from './MessageItem.vue'
import SourceCard from './SourceCard.vue'
import { error as logError } from '../../utils/logger.js'

const {
  sessions,
  currentSession,
  messages,
  loading,
  streamingContent,
  ragSteps,
  fetchSessions,
  createSession,
  selectSession,
  sendMessage,
  resetRagSteps,
} = useChat()

const ChatState = {
  IDLE: 'idle',
  THINKING: 'thinking',
  STREAMING: 'streaming',
}

const chatState = ref(ChatState.IDLE)
const showRagSteps = ref(true)
const inputMessage = ref('')
const messagesContainer = ref(null)

const currentRagStep = computed(() => {
  const runningStep = ragSteps.value.find((step) => step.status === 'running')
  return runningStep || ragSteps.value[ragSteps.value.length - 1]
})

function getStepStatusClass(status) {
  if (status === 'running') return 'step-running'
  if (status === 'completed') return 'step-completed'
  return 'step-pending'
}

function getStepStatusIcon(status) {
  if (status === 'running') return '⏳'
  if (status === 'completed') return '✓'
  return '○'
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function handleCreateSession() {
  const title = `会话 ${new Date().toLocaleString('zh-CN')}`
  const result = await createSession(title)

  if (result?.ok && result?.data) {
    await selectSession(result.data)
  }
}

async function handleSendMessage() {
  if (!inputMessage.value.trim() || loading.value.send) return

  if (!currentSession.value) {
    await handleCreateSession()
  }

  if (!currentSession.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  messages.value.push({
    role: 'user',
    content: userMessage,
    created_at: new Date().toISOString(),
  })

  scrollToBottom()
  loading.value.send = true
  streamingContent.value = ''
  resetRagSteps()
  chatState.value = ChatState.THINKING
  showRagSteps.value = true

  try {
    let fullContent = ''

    for await (const event of sendMessage(currentSession.value.id, userMessage)) {
      if (event.type === 'chunk') {
        if (chatState.value === ChatState.THINKING) {
          chatState.value = ChatState.STREAMING
        }

        fullContent += event.content
        streamingContent.value = fullContent
        scrollToBottom()
      } else if (event.type === 'done') {
        messages.value.push({
          role: 'assistant',
          content: fullContent,
          trace_id: event.trace_id,
          sources: event.sources,
          created_at: new Date().toISOString(),
        })

        streamingContent.value = ''
        chatState.value = ChatState.IDLE
        resetRagSteps()
      } else if (event.type === 'error') {
        messages.value.push({
          role: 'assistant',
          content: `错误: ${event.message}`,
          created_at: new Date().toISOString(),
        })

        chatState.value = ChatState.IDLE
        resetRagSteps()
      } else if (event.type === 'rag_step') {
        scrollToBottom()
      }
    }
  } catch (error) {
    logError('Stream error:', error)
    messages.value.push({
      role: 'assistant',
      content: `错误: ${error.message}`,
      created_at: new Date().toISOString(),
    })

    chatState.value = ChatState.IDLE
    resetRagSteps()
  }

  loading.value.send = false
  scrollToBottom()
}

onMounted(async () => {
  await fetchSessions()

  if (!currentSession.value && sessions.value.length > 0) {
    await selectSession(sessions.value[0])
  }
})
</script>

<template>
  <section class="chat-main-area">
    <div v-if="!currentSession" class="chat-empty-state">
      <p>请选择或创建一个会话开始提问。</p>
      <el-button type="primary" @click="handleCreateSession">创建会话</el-button>
    </div>

    <template v-else>
      <header class="chat-main-header">
        <h3>{{ currentSession.title }}</h3>
        <span>Session ID: {{ currentSession.id }}</span>
      </header>

      <div ref="messagesContainer" class="chat-messages">
        <div v-if="loading.messages" class="messages-state">加载消息中...</div>
        <div v-else-if="messages.length === 0" class="messages-state">开始对话吧</div>

        <template v-else>
          <div v-for="(msg, idx) in messages" :key="idx">
            <MessageItem :message="msg" />
            <div v-if="msg.sources?.length" class="message-sources">
              <div class="source-title">来源引用:</div>
              <SourceCard v-for="(source, sourceIdx) in msg.sources" :key="sourceIdx" :source="source" />
            </div>
          </div>

          <div v-if="chatState === ChatState.THINKING && ragSteps.length > 0" class="thinking-container">
            <div class="thinking-bubble">
              <div class="thinking-header" @click="showRagSteps = !showRagSteps">
                <span class="thinking-icon">🤔</span>
                <span class="thinking-text">{{ currentRagStep?.message || '正在思考...' }}</span>
                <span class="thinking-toggle">{{ showRagSteps ? '▼' : '▶' }}</span>
              </div>

              <div v-if="showRagSteps" class="rag-steps-list">
                <div
                  v-for="step in ragSteps"
                  :key="step.step"
                  class="rag-step-item"
                  :class="getStepStatusClass(step.status)"
                >
                  <span class="step-icon">{{ step.icon }}</span>
                  <span class="step-label">{{ step.label }}</span>
                  <span class="step-status-icon">{{ getStepStatusIcon(step.status) }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="chatState === ChatState.STREAMING || streamingContent" class="streaming-container">
            <div class="streaming-bubble">
              <div class="streaming-content">
                <div class="content-text">{{ streamingContent }}</div>
                <span class="cursor-blink">|</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="chat-input">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入消息..."
          :disabled="loading.send"
          @keyup.enter.prevent="handleSendMessage"
        />
        <el-button type="primary" :disabled="loading.send || !inputMessage.trim()" @click="handleSendMessage">
          {{ loading.send ? '发送中...' : '发送' }}
        </el-button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.chat-main-area {
  min-height: 0;
  height: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-elevated);
  display: flex;
  flex-direction: column;
}

.chat-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-secondary);
}

.chat-main-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.chat-main-header h3 {
  margin: 0;
  font-size: 15px;
}

.chat-main-header span {
  font-size: 12px;
  color: var(--color-text-muted);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.messages-state {
  color: var(--color-text-secondary);
  text-align: center;
  padding: 28px 0;
}

.message-sources {
  margin: 0 0 16px;
}

.source-title {
  font-size: 12px;
  color: var(--color-text-muted);
}

.chat-input {
  border-top: 1px solid var(--color-border);
  padding: 12px;
  display: grid;
  gap: 8px;
}

.thinking-container,
.streaming-container {
  margin-bottom: 16px;
}

.thinking-bubble,
.streaming-bubble {
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.thinking-text {
  flex: 1;
  font-size: 13px;
}

.rag-steps-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rag-step-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.step-completed {
  color: var(--color-success);
}

.step-running {
  color: var(--color-accent);
}

.streaming-content {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--color-text-primary);
}

.content-text {
  white-space: pre-wrap;
}

.cursor-blink {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%,
  50% {
    opacity: 1;
  }

  51%,
  100% {
    opacity: 0;
  }
}

@media (min-width: 768px) {
  .chat-main-area {
    min-height: min(760px, calc(100vh - 250px));
  }
}

@media (max-width: 767px) {
  .chat-main-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chat-main-area {
    min-height: 500px;
  }
}
</style>
