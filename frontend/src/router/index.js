import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import HomeView from '../views/HomeView.vue'
import CuratorView from '../views/CuratorView.vue'
import ExhibitsView from '../views/ExhibitsView.vue'
import AdminView from '../views/AdminView.vue'
import NotFoundView from '../views/NotFoundView.vue'
import DesignSystemView from '../views/DesignSystemView.vue'
import TourView from '../views/TourView.vue'
import ProfileSettings from '../components/profile/ProfileSettings.vue'
import MiniProgramControlPanel from '../components/admin/MiniProgramControlPanel.vue'
import HallManager from '../components/admin/HallManager.vue'
import ExhibitManager from '../components/admin/ExhibitManager.vue'
import TourPathManager from '../components/admin/TourPathManager.vue'
import PromptManager from '../components/admin/PromptManager.vue'
import DocumentManager from '../components/admin/DocumentManager.vue'
import LLMTraceManager from '../components/admin/LLMTraceManager.vue'
import TtsPersonaManager from '../components/admin/TtsPersonaManager.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: {
      title: '工作台',
      icon: 'HomeFilled',
    },
  },
  {
    path: '/tour',
    name: 'tour',
    component: TourView,
    meta: {
      title: 'AI 导览',
      icon: 'Compass',
      requiresAuth: false,
    },
  },
  {
    path: '/curator',
    name: 'curator',
    component: CuratorView,
    meta: {
      title: '导览助手',
      icon: 'MapLocation',
      requiresAuth: true,
      sidebar: 'tour-plan',
    },
  },
  {
    path: '/exhibits',
    name: 'exhibits',
    component: ExhibitsView,
    meta: {
      title: '展品浏览',
      icon: 'Collection',
      requiresAuth: true,
      sidebar: 'exhibit-filters',
    },
  },
  {
    path: '/profile',
    name: 'profile',
    component: ProfileSettings,
    meta: {
      title: '个人设置',
      icon: 'User',
      requiresAuth: true,
    },
  },
  {
    path: '/design-system',
    name: 'design-system',
    component: DesignSystemView,
    meta: {
      title: '设计系统',
      icon: 'Brush',
    },
  },
  {
    path: '/admin',
    component: AdminView,
    meta: {
      title: '管理后台',
      icon: 'Setting',
      requiresAuth: true,
      requiresAdmin: true,
      sidebar: 'admin-nav',
    },
    children: [
      {
        path: '',
        redirect: '/admin/overview',
      },
      {
        path: 'overview',
        name: 'admin-overview',
        component: MiniProgramControlPanel,
        meta: {
          title: '小程序闭环',
        },
      },
      {
        path: 'documents',
        name: 'admin-documents',
        component: DocumentManager,
        meta: {
          title: '知识库管理',
        },
      },
      {
        path: 'halls',
        name: 'admin-halls',
        component: HallManager,
        meta: {
          title: '展厅设置',
        },
      },
      {
        path: 'exhibits',
        name: 'admin-exhibits',
        component: ExhibitManager,
        meta: {
          title: '展品管理',
        },
      },
      {
        path: 'tour-paths',
        name: 'admin-tour-paths',
        component: TourPathManager,
        meta: {
          title: '路线管理',
        },
      },
      {
        path: 'prompts',
        name: 'admin-prompts',
        component: PromptManager,
        meta: {
          title: '提示词管理',
        },
      },
      {
        path: 'llm-traces',
        name: 'admin-llm-traces',
        component: LLMTraceManager,
        meta: {
          title: 'LLM 调用追踪',
        },
      },
      {
        path: 'tts-personas',
        name: 'admin-tts-personas',
        component: TtsPersonaManager,
        meta: {
          title: '语音角色管理',
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: NotFoundView,
    meta: {
      title: '页面未找到',
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const auth = useAuth()

  if (to.meta.requiresAuth && !auth.isAuthenticated.value) {
    next({ name: 'home', query: { redirect: to.fullPath } })
    return
  }

  if (to.meta.requiresAdmin && !auth.isAdmin.value) {
    next({ name: 'home' })
    return
  }

  document.title = to.meta.title ? `${to.meta.title} - MuseAI` : 'MuseAI'
  next()
})

export default router
