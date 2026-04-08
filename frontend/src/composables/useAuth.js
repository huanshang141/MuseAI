import { ref, computed } from 'vue'
import { api } from '../api/index.js'

// User info is stored in localStorage for UI purposes, but the token is stored
// in an HttpOnly cookie managed by the backend for security.
const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const userRole = ref(localStorage.getItem('user_role') || null)

export function useAuth() {
  // isAuthenticated is based on user presence (token is in HttpOnly cookie)
  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => userRole.value === 'admin')

  function setAuth(newUser, role = null) {
    user.value = newUser
    userRole.value = role
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

  function clearAuth() {
    user.value = null
    userRole.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('user_role')
  }

  async function register(email, password) {
    const result = await api.auth.register(email, password)
    return result
  }

  async function login(email, password) {
    const result = await api.auth.login(email, password)
    if (result.ok) {
      // Token is now stored in HttpOnly cookie by backend
      // Store email and role as user info for UI purposes
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
    clearAuth()
  }

  // getToken is deprecated - token is now in HttpOnly cookie
  // Keeping for backward compatibility but returns null
  function getToken() {
    return null
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
