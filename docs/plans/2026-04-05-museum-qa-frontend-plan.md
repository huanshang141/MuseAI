# 博物馆展品问答助手前端实施计划
**Status:** completed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将现有 API 测试页面重构为博物馆展品问答助手应用，使用 Element Plus 构建专业 UI，覆盖所有后端 API。

**Architecture:** Vue 3 Composition API + Element Plus，左侧知识库管理面板 + 右侧聊天主区域，流式问答 + 文档管理。

**Tech Stack:** Vue 3, Vite, Element Plus, fetch API, SSE

---

## Task 1: 安装 Element Plus 依赖

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.js`

**Step 1: 安装 Element Plus**

Run: `cd frontend && npm install element-plus @element-plus/icons-vue`

Expected: 依赖安装成功

**Step 2: 更新 main.js 引入 Element Plus**

Modify `frontend/src/main.js`:

```javascript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.mount('#app')
```

**Step 3: 验证安装成功**

Run: `cd frontend && npm run dev`

Expected: 开发服务器启动，浏览器中能看到 Element Plus 样式

**Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.js
git commit -m "chore: add Element Plus UI library"
```

---

## Task 2: 重构主布局 App.vue

**Files:**
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/components/layout/AppHeader.vue`
- Create: `frontend/src/components/layout/AppSidebar.vue`
- Create: `frontend/src/styles/custom.css`

**Step 1: 创建自定义样式文件**

Create `frontend/src/styles/custom.css`:

```css
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  height: 60px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.app-sidebar {
  width: 280px;
  border-right: 1px solid #e4e7ed;
  background: #fafafa;
  display: flex;
  flex-direction: column;
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.logo-icon {
  font-size: 24px;
}
```

**Step 2: 创建 AppHeader 组件**

Create `frontend/src/components/layout/AppHeader.vue`:

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/index.js'

const healthStatus = ref('unknown')

async function checkHealth() {
  const result = await api.health()
  healthStatus.value = result.ok ? 'healthy' : 'unhealthy'
}

onMounted(checkHealth)
</script>

<template>
  <div class="app-header">
    <div class="logo">
      <el-icon class="logo-icon"><Collection /></el-icon>
      <span>MuseAI - 博物馆展品问答助手</span>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
      <el-tag :type="healthStatus === 'healthy' ? 'success' : 'danger'" size="small">
        {{ healthStatus === 'healthy' ? '服务正常' : '服务异常' }}
      </el-tag>
    </div>
  </div>
</template>
```

**Step 3: 创建 AppSidebar 占位组件**

Create `frontend/src/components/layout/AppSidebar.vue`:

```vue
<script setup>
</script>

<template>
  <div class="app-sidebar">
    <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
      <h3 style="margin: 0; font-size: 16px;">知识库管理</h3>
    </div>
    <div style="flex: 1; padding: 16px;">
      <el-empty description="知识库模块开发中" />
    </div>
  </div>
</template>
```

**Step 4: 重构 App.vue 主布局**

Modify `frontend/src/App.vue`:

```vue
<script setup>
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
</script>

<template>
  <div class="app-container">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <div class="app-main">
        <ChatPanel />
      </div>
    </div>
  </div>
</template>

<style>
@import './styles/custom.css';
</style>
```

**Step 5: 验证布局正常**

Run: `cd frontend && npm run dev`

Expected: 看到顶部导航、左侧边栏、右侧聊天区域

**Step 6: Commit**

```bash
git add frontend/src/App.vue frontend/src/components/layout/ frontend/src/styles/
git commit -m "feat: refactor main layout with header and sidebar"
```

---

## Task 3: 实现文档上传组件

**Files:**
- Create: `frontend/src/components/knowledge/DocumentUpload.vue`
- Create: `frontend/src/composables/useDocuments.js`

**Step 1: 创建文档管理 composable**

Create `frontend/src/composables/useDocuments.js`:

```javascript
import { ref } from 'vue'
import { api } from '../api/index.js'

export function useDocuments() {
  const documents = ref([])
  const loading = ref(false)

  async function fetchDocuments() {
    loading.value = true
    const result = await api.documents.list()
    loading.value = false
    if (result.ok) {
      documents.value = result.data.documents
    }
    return result
  }

  async function uploadDocument(file) {
    const result = await api.documents.upload(file)
    if (result.ok) {
      documents.value.unshift(result.data)
    }
    return result
  }

  async function deleteDocument(docId) {
    const result = await api.documents.delete(docId)
    if (result.ok) {
      documents.value = documents.value.filter(d => d.id !== docId)
    }
    return result
  }

  async function getDocumentStatus(docId) {
    return await api.documents.status(docId)
  }

  return {
    documents,
    loading,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    getDocumentStatus,
  }
}
```

**Step 2: 创建文档上传组件**

Create `frontend/src/components/knowledge/DocumentUpload.vue`:

```vue
<script setup>
import { ref } from 'vue'
import { useDocuments } from '../../composables/useDocuments.js'
import { ElMessage } from 'element-plus'

const { uploadDocument } = useDocuments()
const uploadRef = ref(null)

async function handleUpload(options) {
  const result = await uploadDocument(options.file)
  if (result.ok) {
    ElMessage.success('文档上传成功')
  } else {
    ElMessage.error(`上传失败: ${result.data.detail || '未知错误'}`)
  }
}

function handleExceed() {
  ElMessage.warning('一次只能上传一个文件')
}
</script>

<template>
  <div style="padding: 16px;">
    <el-upload
      ref="uploadRef"
      :auto-upload="true"
      :show-file-list="false"
      :on-exceed="handleExceed"
      :http-request="handleUpload"
      accept=".txt,.md,.pdf"
      drag
    >
      <el-icon style="font-size: 48px; color: #909399;"><UploadFilled /></el-icon>
      <div style="margin-top: 8px; color: #606266;">
        拖拽文件到此处或 <em style="color: #409EFF;">点击上传</em>
      </div>
      <template #tip>
        <div style="color: #909399; font-size: 12px; margin-top: 8px;">
          支持 .txt, .md, .pdf 文件，最大 50MB
        </div>
      </template>
    </el-upload>
  </div>
</template>
```

**Step 3: 验证上传组件**

Run: `cd frontend && npm run dev`

Expected: 看到拖拽上传区域，可以上传文件

**Step 4: Commit**

```bash
git add frontend/src/composables/useDocuments.js frontend/src/components/knowledge/DocumentUpload.vue
git commit -m "feat: add document upload component with drag-drop support"
```

---

## Task 4: 实现文档列表组件

**Files:**
- Create: `frontend/src/components/knowledge/DocumentList.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

**Step 1: 创建文档列表组件**

Create `frontend/src/components/knowledge/DocumentList.vue`:

```vue
<script setup>
import { onMounted } from 'vue'
import { useDocuments } from '../../composables/useDocuments.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const { documents, loading, fetchDocuments, deleteDocument, getDocumentStatus } = useDocuments()

const statusMap = {
  processing: { type: 'warning', text: '处理中' },
  completed: { type: 'success', text: '已完成' },
  failed: { type: 'danger', text: '失败' },
}

async function handleDelete(doc) {
  try {
    await ElMessageBox.confirm('确定删除此文档？', '确认删除', { type: 'warning' })
    const result = await deleteDocument(doc.id)
    if (result.ok) {
      ElMessage.success('删除成功')
    } else {
      ElMessage.error('删除失败')
    }
  } catch {
    // 用户取消
  }
}

async function handleViewStatus(doc) {
  const result = await getDocumentStatus(doc.id)
  if (result.ok) {
    const data = result.data
    ElMessage.success(`文档状态: ${data.status}, 分块数: ${data.chunk_count}`)
  } else {
    ElMessage.error('获取状态失败')
  }
}

onMounted(fetchDocuments)
</script>

<template>
  <div style="flex: 1; overflow-y: auto;">
    <div v-if="loading" style="padding: 20px; text-align: center;">
      <el-icon class="is-loading" style="font-size: 24px;"><Loading /></el-icon>
    </div>
    <div v-else-if="documents.length === 0" style="padding: 20px; text-align: center; color: #909399;">
      暂无文档
    </div>
    <div v-else>
      <div
        v-for="doc in documents"
        :key="doc.id"
        style="padding: 12px 16px; border-bottom: 1px solid #e4e7ed;"
      >
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="flex: 1; overflow: hidden;">
            <div style="font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <el-icon style="margin-right: 4px;"><Document /></el-icon>
              {{ doc.filename }}
            </div>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ new Date(doc.created_at).toLocaleString('zh-CN') }}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-tag :type="statusMap[doc.status]?.type || 'info'" size="small">
              {{ statusMap[doc.status]?.text || doc.status }}
            </el-tag>
            <el-button-group size="small">
              <el-button @click="handleViewStatus(doc)" :icon="View" />
              <el-button @click="handleDelete(doc)" :icon="Delete" type="danger" />
            </el-button-group>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

**Step 2: 更新 AppSidebar 集成文档组件**

Modify `frontend/src/components/layout/AppSidebar.vue`:

```vue
<script setup>
import DocumentUpload from '../knowledge/DocumentUpload.vue'
import DocumentList from '../knowledge/DocumentList.vue'
</script>

<template>
  <div class="app-sidebar">
    <div style="padding: 16px; border-bottom: 1px solid #e4e7ed;">
      <h3 style="margin: 0; font-size: 16px;">知识库管理</h3>
    </div>
    <DocumentUpload />
    <DocumentList />
  </div>
</template>
```

**Step 3: 验证文档列表**

Run: `cd frontend && npm run dev`

Expected: 左侧显示文档上传和列表，可以上传、查看状态、删除

**Step 4: Commit**

```bash
git add frontend/src/components/knowledge/DocumentList.vue frontend/src/components/layout/AppSidebar.vue
git commit -m "feat: add document list with status and delete actions"
```

---

## Task 5: 重构聊天组件

**Files:**
- Modify: `frontend/src/components/ChatPanel.vue`
- Create: `frontend/src/composables/useChat.js`

**Step 1: 创建聊天管理 composable**

Create `frontend/src/composables/useChat.js`:

```javascript
import { ref } from 'vue'
import { api } from '../api/index.js'

export function useChat() {
  const sessions = ref([])
  const currentSession = ref(null)
  const messages = ref([])
  const loading = ref({ sessions: false, messages: false, send: false })

  async function fetchSessions() {
    loading.value.sessions = true
    const result = await api.chat.listSessions()
    loading.value.sessions = false
    if (result.ok) {
      sessions.value = result.data
    }
    return result
  }

  async function createSession(title) {
    const result = await api.chat.createSession(title)
    if (result.ok) {
      sessions.value.unshift(result.data)
      currentSession.value = result.data
      messages.value = []
    }
    return result
  }

  async function selectSession(session) {
    currentSession.value = session
    await fetchMessages(session.id)
  }

  async function fetchMessages(sessionId) {
    loading.value.messages = true
    const result = await api.chat.getMessages(sessionId)
    loading.value.messages = false
    if (result.ok) {
      messages.value = result.data
    }
    return result
  }

  async function deleteSession(sessionId) {
    const result = await api.chat.deleteSession(sessionId)
    if (result.ok) {
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSession.value?.id === sessionId) {
        currentSession.value = null
        messages.value = []
      }
    }
    return result
  }

  async function* sendMessage(sessionId, message) {
    yield* api.chat.askStream(sessionId, message)
  }

  return {
    sessions,
    currentSession,
    messages,
    loading,
    fetchSessions,
    createSession,
    selectSession,
    fetchMessages,
    deleteSession,
    sendMessage,
  }
}
```

**Step 2: 重构 ChatPanel 使用 composable**

Modify `frontend/src/components/ChatPanel.vue`，保持现有的流式逻辑，但使用 `useChat` composable。

**Step 3: 验证聊天功能**

Run: `cd frontend && npm run dev`

Expected: 聊天功能正常，会话管理正常

**Step 4: Commit**

```bash
git add frontend/src/composables/useChat.js frontend/src/components/ChatPanel.vue
git commit -m "refactor: extract chat logic to composable"
```

---

## Task 6: 创建消息展示组件

**Files:**
- Create: `frontend/src/components/chat/MessageItem.vue`
- Create: `frontend/src/components/chat/SourceCard.vue`

**Step 1: 创建消息项组件**

Create `frontend/src/components/chat/MessageItem.vue`:

```vue
<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
  },
})

function formatTime(isoString) {
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
      background: message.role === 'user' ? '#409EFF' : '#F4F4F5',
      color: message.role === 'user' ? '#fff' : '#303133',
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
```

**Step 2: 创建来源卡片组件**

Create `frontend/src/components/chat/SourceCard.vue`:

```vue
<script setup>
import { ref } from 'vue'

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
        <el-tag size="small" type="info">
          相似度: {{ (source.score || 0).toFixed(2) }}
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
```

**Step 3: Commit**

```bash
git add frontend/src/components/chat/
git commit -m "feat: add message item and source card components"
```

---

## Task 7: 集成所有组件并测试

**Files:**
- Modify: `frontend/src/components/ChatPanel.vue`
- Modify: `frontend/src/App.vue`

**Step 1: 更新 ChatPanel 使用新组件**

Modify `frontend/src/components/ChatPanel.vue` 引入 `MessageItem` 和 `SourceCard`。

**Step 2: 全面测试所有 API**

Run: `cd frontend && npm run dev`

测试清单：
- [ ] 上传文档
- [ ] 查看文档列表
- [ ] 查看文档状态
- [ ] 删除文档
- [ ] 创建会话
- [ ] 切换会话
- [ ] 删除会话
- [ ] 发送消息（流式）
- [ ] 查看来源引用

**Step 3: 修复发现的问题**

**Step 4: Final Commit**

```bash
git add frontend/
git commit -m "feat: complete museum QA frontend application"
```

---

## Success Verification

完成所有任务后，运行以下验证：

```bash
# 1. 启动后端服务
**Status:** completed
cd backend && python -m uvicorn app.main:app --reload

# 2. 启动前端服务
cd frontend && npm run dev

# 3. 浏览器访问 http://localhost:5173
# 4. 验证所有功能正常工作
```

---

## Notes

- 所有组件使用 Element Plus，保持 UI 风格一致
- API 调用复用现有 `frontend/src/api/index.js`
- 流式问答保持现有 SSE 实现
- 错误处理使用 `ElMessage` 和 `ElNotification`
