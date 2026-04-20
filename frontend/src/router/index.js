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
    path: '/tour',
    name: 'tour',
    component: () => import('../views/TourView.vue'),
    meta: { requiresAuth: false }
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
        path: 'documents',
        name: 'admin-documents',
        component: () => import('../components/admin/DocumentManager.vue'),
        meta: { title: '知识库管理' }
      },
      {
        path: 'halls',
        name: 'admin-halls',
        component: () => import('../components/admin/HallManager.vue'),
        meta: { title: '展厅设置' }
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
      },
      {
        path: 'prompts',
        name: 'admin-prompts',
        component: () => import('../components/admin/PromptManager.vue'),
        meta: { title: '提示词管理' }
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
  const { isAuthenticated, isAdmin } = useAuth()

  if (to.meta.requiresAuth && !isAuthenticated.value) {
    next('/')
    return
  }

  if (to.meta.requiresAdmin && !isAdmin.value) {
    next('/')
    return
  }

  next()
})

export default router
