import { ref, computed } from 'vue'
import { api } from '../api/index.js'

const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const userRole = ref(localStorage.getItem('user_role') || null)
const token = ref(localStorage.getItem('auth_token') || null)

export function useAuth() {
  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => userRole.value === 'admin')

  function setAuth(newUser, role = null, authToken = null) {
    user.value = newUser
    userRole.value = role
    token.value = authToken
    if (newUser) {
      localStorage.setItem('user', JSON.stringify(newUser))
    } else {
      localStorage.removeItem('user')
    }
    if (role) {
      localStorage.setItem('user_role', role)
    } else {
      localStorage.removeItem('user_role')
    }
    if (authToken) {
      localStorage.setItem('auth_token', authToken)
    } else {
      localStorage.removeItem('auth_token')
    }
  }

  function clearAuth() {
    user.value = null
    userRole.value = null
    token.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('user_role')
    localStorage.removeItem('auth_token')
    localStorage.removeItem('tour_session_id')
    localStorage.removeItem('tour_session_token')
    localStorage.removeItem('tour_pending_events')
  }

  async function register(email, password) {
    const result = await api.auth.register(email, password)
    return result
  }

  async function login(email, password) {
    const result = await api.auth.login(email, password)
    if (result.ok) {
      const userInfo = { email, role: result.data.role }
      setAuth(userInfo, result.data.role, result.data.access_token)
    }
    return result
  }

  async function logout() {
    try {
      await api.auth.logout()
    } catch {
      // ignore API errors — still clear local state
    }
    clearAuth()
  }

  function getToken() {
    return token.value
  }

  return {
    user,
    userRole,
    isAuthenticated,
    isAdmin,
    register,
    login,
    logout,
    setAuth,
    clearAuth,
    getToken,
  }
}
