import { ref, computed } from 'vue'
import { api } from '../api/index.js'

const token = ref(localStorage.getItem('access_token') || null)
const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const userRole = ref(localStorage.getItem('user_role') || null)

export function useAuth() {
  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => userRole.value === 'admin')

  function setAuth(newToken, newUser, role = null) {
    token.value = newToken
    user.value = newUser
    userRole.value = role
    if (newToken) {
      localStorage.setItem('access_token', newToken)
    } else {
      localStorage.removeItem('access_token')
    }
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
  }

  async function register(email, password) {
    const result = await api.auth.register(email, password)
    return result
  }

  async function login(email, password) {
    const result = await api.auth.login(email, password)
    if (result.ok) {
      // Store token
      token.value = result.data.access_token
      localStorage.setItem('access_token', result.data.access_token)

      // Store email and role as user info
      const userInfo = { email, role: result.data.role }
      user.value = userInfo
      localStorage.setItem('user', JSON.stringify(userInfo))
      userRole.value = result.data.role
      localStorage.setItem('user_role', result.data.role)
    }
    return result
  }

  async function logout() {
    await api.auth.logout()
    setAuth(null, null, null)
  }

  function getToken() {
    return token.value
  }

  return {
    token,
    user,
    userRole,
    isAuthenticated,
    isAdmin,
    register,
    login,
    logout,
    setAuth,
    getToken,
  }
}
