# Frontend Curation Testing Redesign Plan

## Goal

将现有测试前端从单一 Chat 界面改造为支持 Digital Curation Agent System 的完整测试平台，包含：导览助手独立页面、展品浏览、展厅地图可视化、Admin Dashboard。

## Current State Analysis

### 现有架构
```
frontend/
├── src/
│   ├── main.js              # Vue 3 + ElementPlus，无 router
│   ├── App.vue              # 单一页面: Header + Sidebar + ChatPanel
│   ├── api/index.js         # REST API client (health, auth, documents, chat)
│   ├── composables/
│   │   ├── useAuth.js       # 认证状态管理
│   │   ├── useChat.js       # 聊天会话管理
│   │   ├── useDocuments.js  # 文档管理
│   │   └── useCurator.js    # ✅ 策展 API (planTour, generateNarrative, getReflectionPrompts)
│   └── components/
│       ├── layout/
│       │   ├── AppHeader.vue    # Logo + 健康检查 + 用户菜单
│       │   └── AppSidebar.vue   # 知识库管理 (DocumentUpload + DocumentList)
│       ├── auth/
│       │   ├── AuthModal.vue
│       │   ├── LoginForm.vue
│       │   └── RegisterForm.vue
│       ├── knowledge/
│       │   ├── DocumentUpload.vue
│       │   └── DocumentList.vue
│       ├── profile/
│       │   └── ProfileSettings.vue  # ✅ 用户偏好设置
│       ├── chat/
│       │   ├── MessageItem.vue
│       │   └── SourceCard.vue
│       └── ChatPanel.vue    # 主聊天界面
```

### Backend API Endpoints (Confirmed)

**Curator API** (`/api/v1/curator`):
- `POST /plan-tour` → `PlanTourResponse` (plan: str, session_id, etc.)
- `POST /narrative` → `NarrativeResponse` (narrative: str, exhibit_name, etc.)
- `POST /reflection` → `ReflectionResponse` (reflection_prompts: str, etc.)

**Admin API** (`/api/v1/admin`):
- `POST /exhibits` → `ExhibitResponse`
- `GET /exhibits?skip=&limit=&category=&hall=` → `ExhibitListResponse`
- `DELETE /exhibits/{id}` → `DeleteResponse`
- (No update endpoint currently)

**Profile API** (`/api/v1/profile`):
- `GET /` → `ProfileResponse`
- `PUT /` → `ProfileResponse`

**Exhibit Public API** (NEED TO ADD):
- `GET /exhibits` - Public exhibit listing
- `GET /exhibits/{id}` - Public exhibit detail

### 缺失功能
1. ❌ Vue Router - 页面切换
2. ❌ 展品浏览/搜索页面 (Public API)
3. ❌ 展厅地图可视化
4. ❌ 导览助手独立页面 (路线规划 + 讲解展示)
5. ❌ Admin Dashboard
6. ❌ 地图/可视化组件

---

## Architecture Design

### 新架构
```
frontend/
├── src/
│   ├── main.js
│   ├── App.vue                    # 改为 RouterView 容器
│   ├── router/
│   │   └── index.js               # 路由配置
│   ├── api/
│   │   └── index.js               # 扩展: exhibits, admin, curator
│   ├── composables/
│   │   ├── useAuth.js
│   │   ├── useChat.js
│   │   ├── useDocuments.js
│   │   ├── useCurator.js          # 扩展: 添加流式响应支持
│   │   ├── useExhibits.js         # 新增: 展品浏览
│   │   └── useAdmin.js            # 新增: Admin 管理
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.vue      # 修改: 添加导航菜单
│   │   │   ├── AppSidebar.vue     # 修改: 按角色显示不同菜单
│   │   │   └── FloorMap.vue       # 新增: 展厅地图组件
│   │   ├── auth/
│   │   ├── knowledge/
│   │   ├── profile/
│   │   ├── chat/
│   │   ├── curator/               # 新增
│   │   │   ├── TourPlanner.vue    # 路线规划表单
│   │   │   ├── TourPathView.vue   # 路线展示 (列表+地图)
│   │   │   ├── ExhibitCard.vue    # 展品卡片
│   │   │   ├── ExhibitDetail.vue  # 展品详情 + 讲解
│   │   │   └── ReflectionPanel.vue # 反身性问题面板
│   │   ├── exhibits/              # 新增
│   │   │   ├── ExhibitList.vue    # 展品列表 + 搜索
│   │   │   └── ExhibitFilter.vue  # 筛选器
│   │   └── admin/                 # 新增
│   │       ├── AdminLayout.vue
│   │       ├── ExhibitManager.vue # 展品 CRUD
│   │       ├── TourPathManager.vue # 路线 CRUD
│   │       └── FloorMapEditor.vue # 地图编辑器 (简化版)
│   └── views/                     # 新增: 页面级组件
│       ├── HomeView.vue           # 原 ChatPanel
│       ├── CuratorView.vue        # 导览助手主页面
│       ├── ExhibitsView.vue       # 展品浏览页面
│       └── AdminView.vue          # Admin Dashboard
```

### 路由设计
```javascript
/                    -> HomeView (聊天)
/curator             -> CuratorView (导览助手)
  └─ /plan           -> 路线规划
  └─ /path/:id       -> 路线详情
/exhibits            -> ExhibitsView (展品浏览)
  └─ /:id            -> 展品详情
/admin               -> AdminView (Admin Dashboard)
  └─ /exhibits       -> 展品管理
  └─ /tour-paths     -> 路线管理
/profile             -> ProfileSettings (移到这里)
```

### 展厅地图设计
使用 SVG 绘制简化展厅平面图：
- 展厅分层 (floor 1/2/3)
- 展品位置标记 (location_x, location_y)
- 路线高亮显示
- 点击标记显示展品信息

---

## Task 1: Setup Vue Router

**Files:**
- Create: `frontend/src/router/index.js`
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/package.json`

### Step 1: Install vue-router

```bash
cd /home/singer/MuseAI/frontend
npm install vue-router@4
```

### Step 2: Create router configuration

Create `frontend/src/router/index.js`:

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { title: '智能问答', icon: 'ChatDotRound' }
  },
  {
    path: '/curator',
    name: 'curator',
    component: () => import('../views/CuratorView.vue'),
    meta: { title: '导览助手', icon: 'MapLocation', requiresAuth: true }
  },
  {
    path: '/exhibits',
    name: 'exhibits',
    component: () => import('../views/ExhibitsView.vue'),
    meta: { title: '展品浏览', icon: 'Collection', requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('../components/profile/ProfileSettings.vue'),
    meta: { title: '个人设置', icon: 'User', requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { title: '管理后台', icon: 'Setting', requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: '',
        redirect: '/admin/exhibits'
      },
      {
        path: 'exhibits',
        name: 'admin-exhibits',
        component: () => import('../components/admin/ExhibitManager.vue'),
        meta: { title: '展品管理' }
      },
      {
        path: 'tour-paths',
        name: 'admin-tour-paths',
        component: () => import('../components/admin/TourPathManager.vue'),
        meta: { title: '路线管理' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guards
router.beforeEach((to, from, next) => {
  const { isAuthenticated, user } = useAuth()
  
  if (to.meta.requiresAuth && !isAuthenticated.value) {
    next('/')
    return
  }
  
  if (to.meta.requiresAdmin && user.value?.email !== 'admin@museai.com') {
    next('/')
    return
  }
  
  next()
})

export default router
```

### Step 3: Update main.js

Modify `frontend/src/main.js`:

```javascript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router/index.js'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus)
app.use(router)
app.mount('#app')
```

### Step 4: Update App.vue

Rewrite `frontend/src/App.vue`:

```vue
<script setup>
import { ref, provide } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppSidebar from './components/layout/AppSidebar.vue'
import AuthModal from './components/auth/AuthModal.vue'
import { useAuth } from './composables/useAuth.js'

const route = useRoute()
const { isAuthenticated } = useAuth()

const showAuthModal = ref(false)
provide('showAuthModal', (show = true) => {
  showAuthModal.value = show
})
</script>

<template>
  <div class="app-container">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <div class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
    <AuthModal v-model:visible="showAuthModal" />
  </div>
</template>

<style>
@import './styles/custom.css';

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: #f5f7fa;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
```

### Step 5: Create views directory structure

```bash
mkdir -p frontend/src/views
```

---

## Task 2: Create Core Views

**Files:**
- Create: `frontend/src/views/HomeView.vue` (原 ChatPanel 迁移)
- Create: `frontend/src/views/CuratorView.vue`
- Create: `frontend/src/views/ExhibitsView.vue`
- Create: `frontend/src/views/AdminView.vue`

### Step 1: Create HomeView (Chat)

Create `frontend/src/views/HomeView.vue`:

```vue
<script setup>
import { ref, inject } from 'vue'
import ChatPanel from '../components/ChatPanel.vue'
import { useAuth } from '../composables/useAuth.js'

const { isAuthenticated } = useAuth()
const showAuthModal = inject('showAuthModal')
</script>

<template>
  <div class="home-view">
    <div v-if="!isAuthenticated" class="auth-required">
      <el-empty description="请先登录以使用完整功能">
        <el-button type="primary" @click="showAuthModal(true)">
          立即登录
        </el-button>
      </el-empty>
    </div>
    <ChatPanel v-else />
  </div>
</template>

<style scoped>
.home-view {
  height: 100%;
}

.auth-required {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
}
</style>
```

### Step 2: Create CuratorView

Create `frontend/src/views/CuratorView.vue`:

```vue
<script setup>
import { ref } from 'vue'
import { useCurator } from '../composables/useCurator.js'
import TourPlanner from '../components/curator/TourPlanner.vue'
import TourPathView from '../components/curator/TourPathView.vue'
import FloorMap from '../components/layout/FloorMap.vue'

const { loading, planTour, generateNarrative, getReflectionPrompts } = useCurator()

const currentPath = ref(null)
const selectedExhibit = ref(null)
const narrative = ref(null)
const reflection = ref(null)

async function handlePlanTour(planData) {
  const result = await planTour(planData.availableTime, planData.interests)
  if (result) {
    currentPath.value = result
  }
}

async function handleSelectExhibit(exhibit) {
  selectedExhibit.value = exhibit
  narrative.value = await generateNarrative(exhibit.id)
  reflection.value = await getReflectionPrompts(exhibit.id)
}
</script>

<template>
  <div class="curator-view">
    <el-row :gutter="20">
      <!-- Left: Tour Planner -->
      <el-col :span="8">
        <TourPlanner 
          :loading="loading"
          @plan="handlePlanTour"
        />
        
        <!-- Path Result -->
        <TourPathView
          v-if="currentPath"
          :path="currentPath"
          @select-exhibit="handleSelectExhibit"
          class="path-result"
        />
      </el-col>
      
      <!-- Center: Floor Map -->
      <el-col :span="10">
        <FloorMap
          :path="currentPath?.path"
          :selected-exhibit="selectedExhibit"
          @select-exhibit="handleSelectExhibit"
        />
      </el-col>
      
      <!-- Right: Exhibit Detail -->
      <el-col :span="6">
        <div v-if="selectedExhibit" class="exhibit-detail-panel">
          <h3>{{ selectedExhibit.name }}</h3>
          
          <!-- Narrative -->
          <el-card v-if="narrative" class="narrative-card">
            <template #header>讲解</template>
            <div class="narrative-content">
              {{ narrative.output || narrative.narrative }}
            </div>
          </el-card>
          
          <!-- Reflection -->
          <el-card v-if="reflection?.questions" class="reflection-card">
            <template #header>思考引导</template>
            <ul>
              <li v-for="(q, i) in reflection.questions" :key="i">
                {{ q }}
              </li>
            </ul>
          </el-card>
        </div>
        
        <el-empty v-else description="选择展品查看详情" />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.curator-view {
  height: 100%;
}

.path-result {
  margin-top: 20px;
}

.exhibit-detail-panel {
  height: 100%;
  overflow-y: auto;
}

.narrative-card,
.reflection-card {
  margin-top: 16px;
}

.narrative-content {
  line-height: 1.8;
  white-space: pre-wrap;
}
</style>
```

### Step 3: Create ExhibitsView

Create `frontend/src/views/ExhibitsView.vue`:

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useExhibits } from '../composables/useExhibits.js'
import ExhibitList from '../components/exhibits/ExhibitList.vue'
import ExhibitFilter from '../components/exhibits/ExhibitFilter.vue'
import FloorMap from '../components/layout/FloorMap.vue'

const { exhibits, loading, fetchExhibits, filterByCategory, filterByHall } = useExhibits()

const selectedExhibit = ref(null)
const viewMode = ref('list') // 'list' | 'map'

onMounted(() => fetchExhibits())

function handleFilter(filters) {
  if (filters.category) {
    filterByCategory(filters.category)
  } else if (filters.hall) {
    filterByHall(filters.hall)
  } else {
    fetchExhibits()
  }
}
</script>

<template>
  <div class="exhibits-view">
    <el-row :gutter="20">
      <el-col :span="6">
        <ExhibitFilter @filter="handleFilter" />
      </el-col>
      
      <el-col :span="18">
        <el-tabs v-model="viewMode">
          <el-tab-pane label="列表视图" name="list">
            <ExhibitList
              :exhibits="exhibits"
              :loading="loading"
              @select="selectedExhibit = $event"
            />
          </el-tab-pane>
          
          <el-tab-pane label="地图视图" name="map">
            <FloorMap
              :exhibits="exhibits"
              :selected-exhibit="selectedExhibit"
              @select-exhibit="selectedExhibit = $event"
            />
          </el-tab-pane>
        </el-tabs>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.exhibits-view {
  height: 100%;
}
</style>
```

### Step 4: Create AdminView

Create `frontend/src/views/AdminView.vue`:

```vue
<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div class="admin-view">
    <el-container>
      <el-aside width="200px">
        <el-menu
          :default-active="route.path"
          router
          class="admin-menu"
        >
          <el-menu-item index="/admin/exhibits">
            <el-icon><Collection /></el-icon>
            <span>展品管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/tour-paths">
            <el-icon><MapLocation /></el-icon>
            <span>路线管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.admin-view {
  height: 100%;
}

.admin-menu {
  height: 100%;
  border-right: none;
}
</style>
```

---

## Task 3: Create Composables

**Files:**
- Create: `frontend/src/composables/useExhibits.js`
- Create: `frontend/src/composables/useAdmin.js`
- Modify: `frontend/src/api/index.js`

### Step 1: Create useExhibits composable

Create `frontend/src/composables/useExhibits.js`:

```javascript
import { ref } from 'vue'
import { api } from '../api/index.js'

const exhibits = ref([])
const currentExhibit = ref(null)
const loading = ref(false)
const error = ref(null)

export function useExhibits() {
  async function fetchExhibits(params = {}) {
    loading.value = true
    error.value = null
    
    const result = await api.exhibits.list(params)
    if (result.ok) {
      exhibits.value = result.data.exhibits || result.data
    } else {
      error.value = result.data?.detail || '获取展品失败'
    }
    
    loading.value = false
    return result
  }

  async function getExhibit(id) {
    loading.value = true
    const result = await api.exhibits.get(id)
    if (result.ok) {
      currentExhibit.value = result.data
    }
    loading.value = false
    return result
  }

  async function filterByCategory(category) {
    return fetchExhibits({ category })
  }

  async function filterByHall(hall) {
    return fetchExhibits({ hall })
  }

  return {
    exhibits,
    currentExhibit,
    loading,
    error,
    fetchExhibits,
    getExhibit,
    filterByCategory,
    filterByHall
  }
}
```

### Step 2: Create useAdmin composable

Create `frontend/src/composables/useAdmin.js`:

```javascript
import { ref } from 'vue'
import { api } from '../api/index.js'

export function useAdmin() {
  const loading = ref(false)
  const error = ref(null)

  // Exhibit management
  async function createExhibit(data) {
    loading.value = true
    const result = await api.admin.createExhibit(data)
    loading.value = false
    return result
  }

  async function updateExhibit(id, data) {
    loading.value = true
    const result = await api.admin.updateExhibit(id, data)
    loading.value = false
    return result
  }

  async function deleteExhibit(id) {
    loading.value = true
    const result = await api.admin.deleteExhibit(id)
    loading.value = false
    return result
  }

  // Tour path management
  async function createTourPath(data) {
    loading.value = true
    const result = await api.admin.createTourPath(data)
    loading.value = false
    return result
  }

  async function updateTourPath(id, data) {
    loading.value = true
    const result = await api.admin.updateTourPath(id, data)
    loading.value = false
    return result
  }

  async function deleteTourPath(id) {
    loading.value = true
    const result = await api.admin.deleteTourPath(id)
    loading.value = false
    return result
  }

  return {
    loading,
    error,
    createExhibit,
    updateExhibit,
    deleteExhibit,
    createTourPath,
    updateTourPath,
    deleteTourPath
  }
}
```

### Step 3: Extend API client

Add to `frontend/src/api/index.js`:

```javascript
export const api = {
  // ... existing endpoints ...

  // Exhibits
  exhibits: {
    list: (params = {}) => request(`/exhibits?${new URLSearchParams(params)}`),
    get: (id) => request(`/exhibits/${id}`),
  },

  // Admin
  admin: {
    // Exhibits
    listExhibits: (params = {}) => request(`/admin/exhibits?${new URLSearchParams(params)}`),
    createExhibit: (data) => request('/admin/exhibits', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    updateExhibit: (id, data) => request(`/admin/exhibits/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
    deleteExhibit: (id) => request(`/admin/exhibits/${id}`, { method: 'DELETE' }),
    
    // Tour Paths
    listTourPaths: () => request('/admin/tour-paths'),
    createTourPath: (data) => request('/admin/tour-paths', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    updateTourPath: (id, data) => request(`/admin/tour-paths/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
    deleteTourPath: (id) => request(`/admin/tour-paths/${id}`, { method: 'DELETE' }),
  }
}
```

---

## Task 4: Create Curator Components

**Files:**
- Create: `frontend/src/components/curator/TourPlanner.vue`
- Create: `frontend/src/components/curator/TourPathView.vue`
- Create: `frontend/src/components/curator/ExhibitCard.vue`
- Create: `frontend/src/components/curator/ReflectionPanel.vue`

### Step 1: Create TourPlanner component

Create `frontend/src/components/curator/TourPlanner.vue`:

```vue
<script setup>
import { ref } from 'vue'

const props = defineProps({
  loading: Boolean
})

const emit = defineEmits(['plan'])

const availableTime = ref(60)
const selectedInterests = ref([])

const interestOptions = [
  { label: '青铜器', value: 'bronze' },
  { label: '书画', value: 'painting' },
  { label: '陶瓷', value: 'ceramics' },
  { label: '玉器', value: 'jade' },
  { label: '金银器', value: 'gold_silver' },
  { label: '雕塑', value: 'sculpture' },
]

function handleSubmit() {
  emit('plan', {
    availableTime: availableTime.value,
    interests: selectedInterests.value
  })
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>规划您的导览路线</span>
      </div>
    </template>
    
    <el-form label-position="top">
      <el-form-item label="可用时间（分钟）">
        <el-slider
          v-model="availableTime"
          :min="30"
          :max="180"
          :step="15"
          show-stops
          show-input
        />
      </el-form-item>
      
      <el-form-item label="感兴趣的类别">
        <el-checkbox-group v-model="selectedInterests">
          <el-checkbox
            v-for="opt in interestOptions"
            :key="opt.value"
            :label="opt.value"
          >
            {{ opt.label }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      
      <el-button
        type="primary"
        :loading="loading"
        :disabled="selectedInterests.length === 0"
        @click="handleSubmit"
      >
        生成路线
      </el-button>
    </el-form>
  </el-card>
</template>
```

### Step 2: Create TourPathView component

Create `frontend/src/components/curator/TourPathView.vue`:

```vue
<script setup>
const props = defineProps({
  path: Object
})

const emit = defineEmits(['select-exhibit'])

function getImportanceType(importance) {
  if (importance >= 5) return 'danger'
  if (importance >= 4) return 'warning'
  return 'info'
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="path-header">
        <span>推荐路线</span>
        <el-tag type="success">
          {{ path.exhibit_count }} 个展品 · {{ path.estimated_duration }} 分钟
        </el-tag>
      </div>
    </template>
    
    <el-timeline>
      <el-timeline-item
        v-for="(exhibit, index) in path.path"
        :key="exhibit.id"
        :type="index === 0 ? 'primary' : ''"
        :hollow="index > 0"
      >
        <div 
          class="exhibit-item"
          @click="emit('select-exhibit', exhibit)"
        >
          <div class="exhibit-header">
            <span class="exhibit-name">{{ index + 1 }}. {{ exhibit.name }}</span>
            <el-tag :type="getImportanceType(exhibit.importance)" size="small">
              {{ exhibit.category }}
            </el-tag>
          </div>
          <div class="exhibit-meta">
            <span>展厅: {{ exhibit.hall }}</span>
            <span>参观时间: {{ exhibit.estimated_time }} 分钟</span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<style scoped>
.path-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.exhibit-item {
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.exhibit-item:hover {
  background: #f5f7fa;
}

.exhibit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.exhibit-name {
  font-weight: 500;
}

.exhibit-meta {
  font-size: 12px;
  color: #909399;
  display: flex;
  gap: 12px;
}
</style>
```

---

## Task 5: Create Floor Map Component

**Files:**
- Create: `frontend/src/components/layout/FloorMap.vue`

Create `frontend/src/components/layout/FloorMap.vue`:

```vue
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  exhibits: Array,
  path: Array,
  selectedExhibit: Object
})

const emit = defineEmits(['select-exhibit'])

const currentFloor = ref(1)
const scale = ref(1)

// Map dimensions (in SVG units)
const MAP_WIDTH = 800
const MAP_HEIGHT = 600

const filteredExhibits = computed(() => {
  const all = props.exhibits || props.path || []
  return all.filter(e => (e.floor || e.location?.floor || 1) === currentFloor.value)
})

const pathData = computed(() => {
  if (!props.path || props.path.length < 2) return ''
  
  const points = props.path
    .filter(e => (e.floor || e.location?.floor || 1) === currentFloor.value)
    .map(e => {
      const x = e.location?.x || e.x || 0
      const y = e.location?.y || e.y || 0
      return `${x * scale.value},${y * scale.value}`
    })
  
  if (points.length < 2) return ''
  return `M ${points.join(' L ')}`
})

function getExhibitPosition(exhibit) {
  const x = exhibit.location?.x || exhibit.x || 0
  const y = exhibit.location?.y || exhibit.y || 0
  return {
    x: x * scale.value,
    y: y * scale.value
  }
}

function isSelected(exhibit) {
  return props.selectedExhibit?.id === exhibit.id
}

function isInPath(exhibit) {
  return props.path?.some(e => e.id === exhibit.id)
}
</script>

<template>
  <el-card class="floor-map-card">
    <template #header>
      <div class="map-header">
        <span>展厅地图</span>
        <div class="map-controls">
          <el-radio-group v-model="currentFloor" size="small">
            <el-radio-button :label="1">一楼</el-radio-button>
            <el-radio-button :label="2">二楼</el-radio-button>
            <el-radio-button :label="3">三楼</el-radio-button>
          </el-radio-group>
          <el-slider v-model="scale" :min="0.5" :max="2" :step="0.1" style="width: 100px; margin-left: 16px;" />
        </div>
      </div>
    </template>
    
    <div class="map-container">
      <svg
        :viewBox="`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`"
        class="floor-map"
      >
        <!-- Background -->
        <rect width="100%" height="100%" fill="#f5f7fa" />
        
        <!-- Grid lines -->
        <g stroke="#e4e7ed" stroke-width="1">
          <line v-for="i in 9" :key="`h${i}`" x1="0" :y1="i * 60" x2="800" :y2="i * 60" />
          <line v-for="i in 13" :key="`v${i}`" :x1="i * 60" y1="0" :x2="i * 60" y2="600" />
        </g>
        
        <!-- Path line -->
        <path
          v-if="pathData"
          :d="pathData"
          fill="none"
          stroke="#409eff"
          stroke-width="3"
          stroke-dasharray="5,5"
        />
        
        <!-- Exhibits -->
        <g
          v-for="exhibit in filteredExhibits"
          :key="exhibit.id"
          class="exhibit-marker"
          :class="{
            'is-selected': isSelected(exhibit),
            'in-path': isInPath(exhibit)
          }"
          @click="emit('select-exhibit', exhibit)"
        >
          <circle
            :cx="getExhibitPosition(exhibit).x"
            :cy="getExhibitPosition(exhibit).y"
            r="12"
            :fill="isSelected(exhibit) ? '#f56c6c' : isInPath(exhibit) ? '#409eff' : '#67c23a'"
            stroke="#fff"
            stroke-width="2"
            class="marker-circle"
          />
          <text
            :x="getExhibitPosition(exhibit).x"
            :y="getExhibitPosition(exhibit).y + 25"
            text-anchor="middle"
            font-size="12"
            fill="#606266"
          >
            {{ exhibit.name }}
          </text>
        </g>
      </svg>
    </div>
    
    <div class="map-legend">
      <div class="legend-item">
        <span class="legend-dot" style="background: #67c23a;"></span>
        <span>普通展品</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: #409eff;"></span>
        <span>路线中的展品</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: #f56c6c;"></span>
        <span>当前选中</span>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.floor-map-card {
  height: 100%;
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.map-controls {
  display: flex;
  align-items: center;
}

.map-container {
  height: 500px;
  overflow: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.floor-map {
  width: 100%;
  height: 100%;
}

.exhibit-marker {
  cursor: pointer;
}

.marker-circle {
  transition: all 0.2s;
}

.exhibit-marker:hover .marker-circle {
  r: 15;
}

.map-legend {
  display: flex;
  gap: 20px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e4e7ed;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #606266;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
</style>
```

---

## Task 6: Create Admin Components

**Files:**
- Create: `frontend/src/components/admin/ExhibitManager.vue`
- Create: `frontend/src/components/admin/TourPathManager.vue`

### Step 1: Create ExhibitManager

Create `frontend/src/components/admin/ExhibitManager.vue`:

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useAdmin } from '../../composables/useAdmin.js'
import { api } from '../../api/index.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const { loading, createExhibit, updateExhibit, deleteExhibit } = useAdmin()

const exhibits = ref([])
const dialogVisible = ref(false)
const isEditing = ref(false)
const formRef = ref(null)

const form = ref({
  name: '',
  description: '',
  location_x: 0,
  location_y: 0,
  floor: 1,
  hall: '',
  category: '',
  era: '',
  importance: 3,
  estimated_visit_time: 10
})

const rules = {
  name: [{ required: true, message: '请输入展品名称', trigger: 'blur' }],
  hall: [{ required: true, message: '请输入展厅', trigger: 'blur' }],
  category: [{ required: true, message: '请输入类别', trigger: 'blur' }]
}

onMounted(fetchExhibits)

async function fetchExhibits() {
  const result = await api.admin.listExhibits()
  if (result.ok) {
    exhibits.value = result.data.exhibits || []
  }
}

function handleAdd() {
  isEditing.value = false
  form.value = {
    name: '',
    description: '',
    location_x: 0,
    location_y: 0,
    floor: 1,
    hall: '',
    category: '',
    era: '',
    importance: 3,
    estimated_visit_time: 10
  }
  dialogVisible.value = true
}

function handleEdit(row) {
  isEditing.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定要删除这个展品吗？', '提示', {
      type: 'warning'
    })
    const result = await deleteExhibit(row.id)
    if (result.ok) {
      ElMessage.success('删除成功')
      fetchExhibits()
    }
  } catch {
    // Cancelled
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const result = isEditing.value
    ? await updateExhibit(form.value.id, form.value)
    : await createExhibit(form.value)

  if (result.ok) {
    ElMessage.success(isEditing.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    fetchExhibits()
  }
}
</script>

<template>
  <div class="exhibit-manager">
    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">
        <el-icon><Plus /></el-icon>
        添加展品
      </el-button>
    </div>

    <el-table :data="exhibits" v-loading="loading" border>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column prop="hall" label="展厅" width="120" />
      <el-table-column prop="floor" label="楼层" width="80" />
      <el-table-column prop="importance" label="重要性" width="90">
        <template #default="{ row }">
          <el-rate :model-value="row.importance" disabled />
        </template>
      </el-table-column>
      <el-table-column prop="estimated_visit_time" label="参观时间(分)" width="110" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑展品' : '添加展品'"
      width="600px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="位置X">
              <el-input-number v-model="form.location_x" :min="0" :max="800" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="位置Y">
              <el-input-number v-model="form.location_y" :min="0" :max="600" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="楼层">
              <el-input-number v-model="form.floor" :min="1" :max="3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="展厅" prop="hall">
              <el-input v-model="form.hall" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="类别" prop="category">
              <el-input v-model="form.category" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="年代">
              <el-input v-model="form.era" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="重要性">
              <el-slider v-model="form.importance" :min="1" :max="5" show-stops />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="参观时间">
              <el-input-number v-model="form.estimated_visit_time" :min="5" :max="60" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.exhibit-manager {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
}
</style>
```

---

## Task 7: Update Layout Components

**Files:**
- Modify: `frontend/src/components/layout/AppHeader.vue`
- Modify: `frontend/src/components/layout/AppSidebar.vue`

### Step 1: Update AppHeader

Add navigation menu to `frontend/src/components/layout/AppHeader.vue`:

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth.js'
import AuthModal from '../auth/AuthModal.vue'
import { api } from '../../api/index.js'
import { User, SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const { user, isAuthenticated, logout } = useAuth()

const healthStatus = ref('checking')
const showAuthModal = ref(false)

const navItems = [
  { path: '/', title: '智能问答', icon: 'ChatDotRound' },
  { path: '/curator', title: '导览助手', icon: 'MapLocation', requiresAuth: true },
  { path: '/exhibits', title: '展品浏览', icon: 'Collection', requiresAuth: true },
]

async function checkHealth() {
  healthStatus.value = 'checking'
  try {
    const result = await api.health()
    healthStatus.value = result.ok ? 'healthy' : 'unhealthy'
  } catch (error) {
    healthStatus.value = 'error'
  }
}

async function handleLogout() {
  await logout()
  router.push('/')
  checkHealth()
}

onMounted(checkHealth)
</script>

<template>
  <div class="app-header">
    <div class="logo-section">
      <div class="logo">
        <el-icon class="logo-icon"><Collection /></el-icon>
        <span>MuseAI</span>
      </div>
      
      <!-- Navigation Menu -->
      <el-menu
        :default-active="route.path"
        mode="horizontal"
        router
        class="nav-menu"
      >
        <el-menu-item
          v-for="item in navItems"
          :key="item.path"
          :index="item.path"
          :disabled="item.requiresAuth && !isAuthenticated"
        >
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </div>
    
    <div class="header-actions">
      <el-tag
        :type="healthStatus === 'healthy' ? 'success' : healthStatus === 'checking' ? 'info' : 'danger'"
        size="small"
      >
        {{ healthStatus === 'healthy' ? '服务正常' : healthStatus === 'checking' ? '检测中...' : '服务异常' }}
      </el-tag>

      <template v-if="isAuthenticated">
        <el-dropdown>
          <div class="user-menu">
            <el-icon><User /></el-icon>
            <span>{{ user?.email || '用户' }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/profile')">
                <el-icon><Setting /></el-icon>
                个人设置
              </el-dropdown-item>
              <el-dropdown-item v-if="user?.email === 'admin@museai.com'" @click="router.push('/admin')">
                <el-icon><Tools /></el-icon>
                管理后台
              </el-dropdown-item>
              <el-dropdown-item divided @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>

      <template v-else>
        <el-button type="primary" size="small" @click="showAuthModal = true">
          登录 / 注册
        </el-button>
      </template>
    </div>

    <AuthModal v-model:visible="showAuthModal" @success="checkHealth" />
  </div>
</template>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: 60px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 40px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: bold;
  color: #409eff;
}

.logo-icon {
  font-size: 24px;
}

.nav-menu {
  border-bottom: none;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
}
</style>
```

---

## Task 8: Testing & Verification

### Step 1: Verify router setup

```bash
cd /home/singer/MuseAI/frontend
npm run dev
```

Expected:
- Navigation between /, /curator, /exhibits works
- Auth guards work (redirect to home if not logged in)
- Admin route protected

### Step 2: Test Curator flow

1. Login
2. Go to /curator
3. Set time and interests
4. Click "生成路线"
5. Verify path displays on map
6. Click exhibit to see narrative and reflection

### Step 3: Test Exhibit browsing

1. Go to /exhibits
2. Test list view and map view
3. Test filters

### Step 4: Test Admin

1. Login as admin
2. Go to /admin/exhibits
3. CRUD operations work

---

## Summary

### New Files (15)
- `frontend/src/router/index.js`
- `frontend/src/views/HomeView.vue`
- `frontend/src/views/CuratorView.vue`
- `frontend/src/views/ExhibitsView.vue`
- `frontend/src/views/AdminView.vue`
- `frontend/src/composables/useExhibits.js`
- `frontend/src/composables/useAdmin.js`
- `frontend/src/components/curator/TourPlanner.vue`
- `frontend/src/components/curator/TourPathView.vue`
- `frontend/src/components/curator/ExhibitCard.vue`
- `frontend/src/components/curator/ReflectionPanel.vue`
- `frontend/src/components/exhibits/ExhibitList.vue`
- `frontend/src/components/exhibits/ExhibitFilter.vue`
- `frontend/src/components/layout/FloorMap.vue`
- `frontend/src/components/admin/ExhibitManager.vue`
- `frontend/src/components/admin/TourPathManager.vue`

### Modified Files (5)
- `frontend/package.json` - add vue-router
- `frontend/src/main.js` - use router
- `frontend/src/App.vue` - router-view
- `frontend/src/api/index.js` - add exhibits, admin endpoints
- `frontend/src/components/layout/AppHeader.vue` - add nav

### Dependencies to Add
```bash
npm install vue-router@4
```

---

**Estimated effort:** 3-4 days
**Priority order:**
1. Router setup + views
2. FloorMap component
3. Curator components + flow
4. Exhibit browsing
5. Admin Dashboard
