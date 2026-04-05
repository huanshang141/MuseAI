import { ref, computed } from 'vue'
import { api } from '../api/index.js'

const token = ref(localStorage.getItem('access_token') || null)
const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

export function useAuth() {
  const isAuthenticated = computed(() => !!token.value)

  function setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
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

      // Store email as user info (backend doesn't have /auth/me endpoint)
      const userInfo = { email }
      user.value = userInfo
      localStorage.setItem('user', JSON.stringify(userInfo))
    }
    return result
  }

  async function logout() {
    await api.auth.logout()
    setAuth(null, null)
  }

  function getToken() {
    return token.value
  }

  return {
    token,
    user,
    isAuthenticated,
    register,
    login,
    logout,
    setAuth,
    getToken,
  }
}
