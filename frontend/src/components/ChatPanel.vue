<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useChat } from '../composables/useChat.js'

const {
  sessions,
  currentSession,
  messages,
  loading,
  streamingContent,
  thinkingStatus,
  fetchSessions,
  createSession,
  selectSession,
  deleteSession,
  sendMessage,
} = useChat()

const inputMessage = ref('')
const messagesContainer = ref(null)

async function handleCreateSession() {
  const title = `会话 ${new Date().toLocaleString('zh-CN')}`
  await createSession(title)
}

async function handleSendMessage() {
  if (!inputMessage.value.trim() || loading.value.send) return
  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  await sendMessage(userMessage)
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
            <div 
              v-for="(msg, idx) in messages" 
              :key="idx"
              :style="{
                marginBottom: '12px',
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }"
            >
              <div :style="{
                maxWidth: '80%',
                padding: '10px 14px',
                borderRadius: '12px',
                background: msg.role === 'user' ? '#4a90d9' : '#f0f0f0',
                color: msg.role === 'user' ? 'white' : '#333',
              }">
                <div style="white-space: pre-wrap; word-break: break-word;">{{ msg.content }}</div>
                <div v-if="msg.trace_id" style="font-size: 10px; margin-top: 6px; opacity: 0.7;">
                  Trace: {{ msg.trace_id }}
                </div>
                <div v-if="msg.sources?.length" style="margin-top: 6px; font-size: 11px; opacity: 0.8;">
                  Sources: {{ msg.sources.length }} 条
                </div>
              </div>
            </div>
            
            <div v-if="thinkingStatus" style="marginBottom: 12px; display: flex; justifyContent: flex-start;">
              <div style="maxWidth: 80%; padding: 10px 14px; borderRadius: 12px; background: #e8f4fd; color: #1976d2; font-size: 13px;">
                <span style="animation: pulse 1s infinite;">⏳</span> {{ thinkingStatus }}
              </div>
            </div>
            
            <div v-if="streamingContent" style="marginBottom: 12px; display: flex; justifyContent: flex-start;">
              <div style="maxWidth: 80%; padding: 10px 14px; borderRadius: 12px; background: #f0f0f0; color: #333;">
                <div style="white-space: pre-wrap; word-break: break-word;">{{ streamingContent }}</div>
                <span style="display: inline-block; animation: blink 1s infinite;">|</span>
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
</style>
