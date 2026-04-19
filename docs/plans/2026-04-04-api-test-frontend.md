# API 测试前端页面实现计划
**Status:** completed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 创建 Vue 3 + Vite 前端页面，用于测试 MuseAI 后端所有 API 端点

**Architecture:** 使用 Vue 3 Composition API 构建单页应用，通过卡片式布局展示各 API 测试功能，使用 fetch API 调用后端

**Tech Stack:** Vue 3, Vite, JavaScript, fetch API

---

## Task 1: 初始化 Vite + Vue 3 项目

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`

**Step 1: 初始化 npm 项目**

Run: `cd frontend && npm init -y`

**Step 2: 安装依赖**

Run: `cd frontend && npm install vue@latest && npm install -D vite @vitejs/plugin-vue`

**Step 3: 创建 vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

**Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MuseAI API 测试面板</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

**Step 5: 创建 src/main.js**

```javascript
import { createApp } from 'vue'
import App from './App.vue'

createApp(App).mount('#app')
```

**Step 6: 更新 package.json 添加 scripts**

在 package.json 中添加:
```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

**Step 7: Commit**

```bash
git add frontend/
git commit -m "chore: init vite + vue 3 project"
```

---

## Task 2: 创建 API 调用封装

**Files:**
- Create: `frontend/src/api/index.js`

**Step 1: 创建 API 模块**

```javascript
const BASE_URL = '/api/v1'

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })
  
  const data = await response.json().catch(() => ({}))
  return {
    ok: response.ok,
    status: response.status,
    data,
  }
}

export const api = {
  health: () => request('/health'),
  ready: () => request('/ready'),
  
  documents: {
    list: () => request('/documents'),
    get: (id) => request(`/documents/${id}`),
    status: (id) => request(`/documents/${id}/status`),
    delete: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
    upload: async (file) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${BASE_URL}/documents/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json().catch(() => ({}))
      return { ok: response.ok, status: response.status, data }
    },
  },
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/
git commit -m "feat: add api module"
```

---

## Task 3: 创建主应用组件

**Files:**
- Create: `frontend/src/App.vue`

**Step 1: 创建 App.vue**

```vue
<script setup>
import { ref } from 'vue'
import { api } from './api/index.js'
import HealthCard from './components/HealthCard.vue'
import DocumentUpload from './components/DocumentUpload.vue'
import DocumentList from './components/DocumentList.vue'
import DocumentActions from './components/DocumentActions.vue'
</script>

<template>
  <div style="max-width: 1200px; margin: 0 auto; padding: 20px; font-family: system-ui, sans-serif;">
    <h1 style="margin-bottom: 24px; color: #333;">MuseAI API 测试面板</h1>
    
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px;">
      <HealthCard />
    </div>
    
    <div style="display: grid; gap: 16px;">
      <DocumentUpload />
      <DocumentList />
      <DocumentActions />
    </div>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: add App.vue main component"
```

---

## Task 4: 创建健康检查组件

**Files:**
- Create: `frontend/src/components/HealthCard.vue`

**Step 1: 创建 HealthCard.vue**

```vue
<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const healthResult = ref(null)
const readyResult = ref(null)
const loading = ref({ health: false, ready: false })

async function checkHealth() {
  loading.value.health = true
  healthResult.value = await api.health()
  loading.value.health = false
}

async function checkReady() {
  loading.value.ready = true
  readyResult.value = await api.ready()
  loading.value.ready = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <h3 style="margin: 0 0 12px 0;">健康检查</h3>
    
    <div style="margin-bottom: 12px;">
      <button @click="checkHealth" :disabled="loading.health" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.health ? '检查中...' : '/health' }}
      </button>
      <pre v-if="healthResult" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-top: 8px; overflow: auto;">{{ JSON.stringify(healthResult, null, 2) }}</pre>
    </div>
    
    <div>
      <button @click="checkReady" :disabled="loading.ready" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.ready ? '检查中...' : '/ready' }}
      </button>
      <pre v-if="readyResult" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-top: 8px; overflow: auto;">{{ JSON.stringify(readyResult, null, 2) }}</pre>
    </div>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend/src/components/HealthCard.vue
git commit -m "feat: add HealthCard component"
```

---

## Task 5: 创建文档上传组件

**Files:**
- Create: `frontend/src/components/DocumentUpload.vue`

**Step 1: 创建 DocumentUpload.vue**

```vue
<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const selectedFile = ref(null)
const uploadResult = ref(null)
const loading = ref(false)

function handleFileChange(event) {
  selectedFile.value = event.target.files[0]
}

async function uploadFile() {
  if (!selectedFile.value) return
  loading.value = true
  uploadResult.value = await api.documents.upload(selectedFile.value)
  loading.value = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <h3 style="margin: 0 0 12px 0;">上传文档</h3>
    
    <div style="display: flex; gap: 12px; align-items: center;">
      <input type="file" @change="handleFileChange" style="flex: 1;" />
      <button @click="uploadFile" :disabled="!selectedFile || loading" style="padding: 8px 16px; cursor: pointer;">
        {{ loading ? '上传中...' : '上传' }}
      </button>
    </div>
    
    <pre v-if="uploadResult" style="background: #f5f5f5; padding: 8px; border-radius: 4px; margin-top: 12px; overflow: auto;">{{ JSON.stringify(uploadResult, null, 2) }}</pre>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend/src/components/DocumentUpload.vue
git commit -m "feat: add DocumentUpload component"
```

---

## Task 6: 创建文档列表组件

**Files:**
- Create: `frontend/src/components/DocumentList.vue`

**Step 1: 创建 DocumentList.vue**

```vue
<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const documents = ref(null)
const loading = ref(false)

async function fetchDocuments() {
  loading.value = true
  const result = await api.documents.list()
  documents.value = result
  loading.value = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h3 style="margin: 0;">文档列表</h3>
      <button @click="fetchDocuments" :disabled="loading" style="padding: 8px 16px; cursor: pointer;">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>
    
    <pre v-if="documents" style="background: #f5f5f5; padding: 8px; border-radius: 4px; overflow: auto;">{{ JSON.stringify(documents, null, 2) }}</pre>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend/src/components/DocumentList.vue
git commit -m "feat: add DocumentList component"
```

---

## Task 7: 创建文档操作组件

**Files:**
- Create: `frontend/src/components/DocumentActions.vue`

**Step 1: 创建 DocumentActions.vue**

```vue
<script setup>
import { ref } from 'vue'
import { api } from '../api/index.js'

const docId = ref('')
const result = ref(null)
const loading = ref({ get: false, status: false, delete: false })

async function getDocument() {
  if (!docId.value) return
  loading.value.get = true
  result.value = await api.documents.get(docId.value)
  loading.value.get = false
}

async function getStatus() {
  if (!docId.value) return
  loading.value.status = true
  result.value = await api.documents.status(docId.value)
  loading.value.status = false
}

async function deleteDocument() {
  if (!docId.value) return
  if (!confirm('确定删除此文档？')) return
  loading.value.delete = true
  result.value = await api.documents.delete(docId.value)
  loading.value.delete = false
}
</script>

<template>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px;">
    <h3 style="margin: 0 0 12px 0;">文档操作</h3>
    
    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
      <input 
        v-model="docId" 
        placeholder="输入文档 ID" 
        style="flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
      />
      <button @click="getDocument" :disabled="!docId || loading.get" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.get ? '...' : '查询' }}
      </button>
      <button @click="getStatus" :disabled="!docId || loading.status" style="padding: 8px 16px; cursor: pointer;">
        {{ loading.status ? '...' : '状态' }}
      </button>
      <button @click="deleteDocument" :disabled="!docId || loading.delete" style="padding: 8px 16px; cursor: pointer; background: #ff4444; color: white; border: none; border-radius: 4px;">
        {{ loading.delete ? '...' : '删除' }}
      </button>
    </div>
    
    <pre v-if="result" style="background: #f5f5f5; padding: 8px; border-radius: 4px; overflow: auto;">{{ JSON.stringify(result, null, 2) }}</pre>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add frontend/src/components/DocumentActions.vue
git commit -m "feat: add DocumentActions component"
```

---

## Task 8: 验证并运行

**Step 1: 启动后端服务**

Run: `cd backend && python -m uvicorn app.main:app --reload --port 8000`

**Step 2: 启动前端开发服务器**

Run: `cd frontend && npm run dev`

**Step 3: 在浏览器中测试**

打开 http://localhost:3000，测试所有 API 功能

**Step 4: 最终 Commit**

```bash
git add -A
git commit -m "feat: complete api test frontend"
```
