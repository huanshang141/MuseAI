<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { useChat } from '../composables/useChat.js'
import MessageItem from './chat/MessageItem.vue'
import SourceCard from './chat/SourceCard.vue'

const {
  sessions,
  currentSession,
  messages,
  loading,
  streamingContent,
  thinkingStatus,
  ragSteps,
  fetchSessions,
  createSession,
  selectSession,
  deleteSession,
  sendMessage,
  resetRagSteps,
} = useChat()

// 状态机状态
const ChatState = {
  IDLE: 'idle',
  THINKING: 'thinking',
  STREAMING: 'streaming',
}

const chatState = ref(ChatState.IDLE)
const showRagSteps = ref(true)

// 当前正在进行的步骤
const currentRagStep = computed(() => {
  const runningStep = ragSteps.value.find(s => s.status === 'running')
  return runningStep || ragSteps.value[ragSteps.value.length - 1]
})

// 获取步骤状态样式
function getStepStatusClass(status) {
  switch (status) {
    case 'running': return 'step-running'
    case 'completed': return 'step-completed'
    default: return 'step-pending'
  }
}

// 获取步骤状态图标
function getStepStatusIcon(status) {
  switch (status) {
    case 'running': return '⏳'
    case 'completed': return '✓'
    default: return '○'
  }
}

const inputMessage = ref('')
const messagesContainer = ref(null)

async function handleCreateSession() {
  const title = `会话 ${new Date().toLocaleString('zh-CN')}`
  console.log('[ChatPanel] Creating session:', title)
  const result = await createSession(title)
  console.log('[ChatPanel] Create session result:', result)
  console.log('[ChatPanel] currentSession after create:', currentSession.value)
}

async function handleSendMessage() {
  if (!inputMessage.value.trim() || loading.value.send || !currentSession.value) return

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
  thinkingStatus.value = ''
  resetRagSteps()
  chatState.value = ChatState.THINKING
  showRagSteps.value = true

  try {
    let fullContent = ''
    for await (const event of sendMessage(currentSession.value.id, userMessage)) {
      if (event.type === 'rag_step') {
        // RAG步骤更新，保持在THINKING状态
        scrollToBottom()
      } else if (event.type === 'chunk') {
        // 第一个chunk，切换到STREAMING状态
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
        thinkingStatus.value = ''
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
      }
    }
  } catch (e) {
    console.error('Stream error:', e)
    messages.value.push({
      role: 'assistant',
      content: `错误: ${e.message}`,
      created_at: new Date().toISOString(),
    })
    chatState.value = ChatState.IDLE
    resetRagSteps()
  }

  loading.value.send = false
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

onMounted(fetchSessions)

// Watch for currentSession changes to debug reactivity
watch(currentSession, (newVal, oldVal) => {
  console.log('[ChatPanel] currentSession changed:', { from: oldVal, to: newVal })
}, { immediate: true })
</script>

<template>
  <div style="display: flex; height: 600px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
    <div style="width: 250px; border-right: 1px solid #ddd; display: flex; flex-direction: column; background: #fafafa;">
      <div style="padding: 12px; border-bottom: 1px solid #eee;">
        <button @click="handleCreateSession" style="width: 100%; padding: 10px; cursor: pointer; background: #4a90d9; color: white; border: none; border-radius: 4px; font-size: 14px;">
          + 新建会话
        </button>
      </div>
      <div style="flex: 1; overflow-y: auto;">
        <div v-if="loading.sessions" style="padding: 20px; text-align: center; color: #999;">加载中...</div>
        <div v-else-if="sessions.length === 0" style="padding: 20px; text-align: center; color: #999;">暂无会话</div>
        <div v-else>
          <div 
            v-for="session in sessions" 
            :key="session.id"
            @click="selectSession(session)"
            :style="{
              padding: '12px',
              cursor: 'pointer',
              borderBottom: '1px solid #eee',
              background: currentSession?.id === session.id ? '#e3f2fd' : 'transparent',
            }"
          >
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px;">
                {{ session.title }}
              </div>
              <button 
                @click.stop="deleteSession(session.id)"
                style="padding: 2px 6px; font-size: 12px; cursor: pointer; background: #ff5252; color: white; border: none; border-radius: 3px; margin-left: 8px;"
              >
                删除
              </button>
            </div>
            <div style="font-size: 11px; color: #999; margin-top: 4px;">
              {{ new Date(session.created_at).toLocaleString('zh-CN') }}
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div style="flex: 1; display: flex; flex-direction: column;">
      <div v-if="!currentSession" style="flex: 1; display: flex; align-items: center; justify-content: center; color: #999;">
        请选择或创建一个会话
      </div>
      
      <template v-else>
        <div style="padding: 12px; border-bottom: 1px solid #eee; background: #fafafa;">
          <div style="font-weight: 500;">{{ currentSession.title }}</div>
          <div style="font-size: 11px; color: #999;">Session ID: {{ currentSession.id }}</div>
        </div>
        
        <div ref="messagesContainer" style="flex: 1; overflow-y: auto; padding: 16px;">
          <div v-if="loading.messages" style="text-align: center; color: #999;">加载消息中...</div>
          <div v-else-if="messages.length === 0" style="text-align: center; color: #999;">开始对话吧</div>
          <div v-else>
            <div v-for="(msg, idx) in messages" :key="idx">
              <MessageItem :message="msg" />
              <div v-if="msg.sources?.length" style="margin-left: 0; margin-bottom: 16px;">
                <div style="font-size: 12px; color: #666; margin-bottom: 8px;">来源引用:</div>
                <SourceCard v-for="(source, sIdx) in msg.sources" :key="sIdx" :source="source" />
              </div>
            </div>
            
            <!-- Thinking State: 显示RAG步骤列表 -->
            <div v-if="chatState === ChatState.THINKING && ragSteps.length > 0" class="thinking-container">
              <div class="thinking-bubble">
                <div class="thinking-header" @click="showRagSteps = !showRagSteps">
                  <span class="thinking-icon">🤔</span>
                  <span class="thinking-text">{{ currentRagStep?.message || '正在思考...' }}</span>
                  <span class="thinking-toggle">{{ showRagSteps ? '▼' : '▶' }}</span>
                </div>
                <div v-if="showRagSteps" class="rag-steps-list">
                  <div
                    v-for="(step, idx) in ragSteps"
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

            <!-- Streaming State: 显示回答内容（同一气泡，隐藏header） -->
            <div v-if="chatState === ChatState.STREAMING || streamingContent" class="streaming-container">
              <div class="streaming-bubble">
                <div v-if="ragSteps.length > 0 && showRagSteps" class="completed-steps-summary" @click="showRagSteps = !showRagSteps">
                  <span class="summary-icon">✓</span>
                  <span class="summary-text">已完成 {{ ragSteps.filter(s => s.status === 'completed').length }} 个步骤</span>
                  <span class="summary-toggle">{{ showRagSteps ? '▼' : '▶' }}</span>
                </div>
                <div v-if="showRagSteps && ragSteps.length > 0" class="rag-steps-list collapsed">
                  <div
                    v-for="(step, idx) in ragSteps"
                    :key="step.step"
                    class="rag-step-item"
                    :class="getStepStatusClass(step.status)"
                  >
                    <span class="step-icon">{{ step.icon }}</span>
                    <span class="step-label">{{ step.label }}</span>
                    <span class="step-status-icon">{{ getStepStatusIcon(step.status) }}</span>
                  </div>
                </div>
                <div class="streaming-content">
                  <div class="content-text">{{ streamingContent }}</div>
                  <span class="cursor-blink">|</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div style="padding: 12px; border-top: 1px solid #eee;">
          <div style="display: flex; gap: 8px;">
            <input 
              v-model="inputMessage"
              @keyup.enter="handleSendMessage"
              placeholder="输入消息..."
              :disabled="loading.send"
              style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;"
            />
            <button 
              @click="handleSendMessage"
              :disabled="loading.send || !inputMessage.trim()"
              style="padding: 10px 20px; cursor: pointer; background: #4a90d9; color: white; border: none; border-radius: 4px; font-size: 14px; opacity: (loading.send || !inputMessage.trim()) ? 0.6 : 1;"
            >
              {{ loading.send ? '发送中...' : '发送' }}
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style>
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Thinking State Styles */
.thinking-container {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-start;
}

.thinking-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #e8f4fd 0%, #f0f7ff 100%);
  border: 1px solid #d0e8f7;
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  color: #1976d2;
  font-size: 14px;
  font-weight: 500;
}

.thinking-icon {
  font-size: 16px;
}

.thinking-text {
  flex: 1;
}

.thinking-toggle {
  font-size: 10px;
  opacity: 0.6;
  transition: transform 0.2s;
}

.rag-steps-list {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(25, 118, 210, 0.15);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rag-steps-list.collapsed {
  margin-top: 8px;
  padding-top: 8px;
}

.rag-step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  transition: all 0.2s ease;
}

.rag-step-item.step-running {
  background: rgba(25, 118, 210, 0.1);
  color: #1976d2;
  font-weight: 500;
}

.rag-step-item.step-completed {
  color: #4caf50;
  opacity: 0.85;
}

.rag-step-item.step-pending {
  color: #9e9e9e;
  opacity: 0.6;
}

.step-icon {
  font-size: 14px;
}

.step-label {
  flex: 1;
}

.step-status-icon {
  font-size: 12px;
}

.step-running .step-status-icon {
  animation: pulse 1.5s infinite;
}

/* Streaming State Styles */
.streaming-container {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-start;
}

.streaming-bubble {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 12px;
  background: #f5f5f5;
  border: 1px solid #e0e0e0;
}

.completed-steps-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  color: #4caf50;
  font-size: 13px;
  font-weight: 500;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(76, 175, 80, 0.15);
  margin-bottom: 8px;
}

.summary-icon {
  font-size: 14px;
}

.summary-text {
  flex: 1;
}

.summary-toggle {
  font-size: 10px;
  opacity: 0.6;
}

.streaming-content {
  display: flex;
  align-items: flex-start;
  color: #333;
  font-size: 14px;
  line-height: 1.6;
}

.content-text {
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
}

.cursor-blink {
  display: inline-block;
  animation: blink 1s infinite;
  color: #666;
  margin-left: 2px;
}
</style>
