<script setup>
import { computed, inject, onMounted } from 'vue'
import { useAuth } from '../../../composables/useAuth.js'
import { useChat } from '../../../composables/useChat.js'

const showAuthModal = inject('showAuthModal', () => {})
const { isAuthenticated } = useAuth()
const {
  sessions,
  currentSession,
  loading,
  fetchSessions,
  createSession,
  selectSession,
  deleteSession,
} = useChat()

const hasSessions = computed(() => sessions.value.length > 0)

async function handleCreateSession() {
  const title = `会话 ${new Date().toLocaleString('zh-CN')}`
  const result = await createSession(title)

  if (result?.ok && result?.data) {
    await selectSession(result.data)
  }
}

async function handleDeleteSession(sessionId) {
  await deleteSession(sessionId)
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  await fetchSessions()

  if (!currentSession.value && hasSessions.value) {
    await selectSession(sessions.value[0])
  }
})
</script>

<template>
  <section class="sidebar-section chat-sessions-sidebar">
    <header class="sidebar-header">
      <h3>对话会话</h3>
      <el-button type="primary" size="small" @click="handleCreateSession">新建</el-button>
    </header>

    <div v-if="loading.sessions" class="sidebar-empty">会话加载中...</div>

    <template v-else-if="!hasSessions">
      <div class="sidebar-empty">暂无会话，点击新建开始提问。</div>
      <el-button v-if="!isAuthenticated" text type="primary" @click="showAuthModal(true)">登录后可同步会话</el-button>
    </template>

    <ul v-else class="session-list">
      <li
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ 'is-active': currentSession?.id === session.id }"
      >
        <button class="session-main" type="button" @click="selectSession(session)">
          <span class="session-title">{{ session.title }}</span>
          <span class="session-time">{{ formatDate(session.created_at) }}</span>
        </button>
        <button class="session-delete" type="button" @click="handleDeleteSession(session.id)">删除</button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.sidebar-section {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 12px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 16px;
}

.sidebar-empty {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.session-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.session-item {
  display: flex;
  gap: 8px;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg-elevated);
}

.session-item.is-active {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-xs);
}

.session-main {
  border: 0;
  background: transparent;
  color: inherit;
  flex: 1;
  min-width: 0;
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  cursor: pointer;
}

.session-title {
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.session-time {
  color: var(--color-text-muted);
  font-size: 11px;
}

.session-delete {
  margin-right: 10px;
  border: 0;
  background: transparent;
  color: var(--color-danger);
  font-size: 12px;
  cursor: pointer;
}
</style>
