import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuth } from '../useAuth.js'

// Mock the api module
vi.mock('../../api/index.js', () => ({
  api: {
    auth: {
      register: vi.fn(),
      login: vi.fn(),
      logout: vi.fn()
    }
  }
}))

// Import the mocked api
import { api } from '../../api/index.js'

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Reset module state by re-importing
    vi.resetModules()
  })

  it('starts with no user when no user in localStorage', async () => {
    // Clear localStorage first
    localStorage.clear()

    // Re-import to get fresh state
    const { useAuth } = await import('../useAuth.js')
    const { user, isAuthenticated } = useAuth()

    expect(user.value).toBeNull()
    expect(isAuthenticated.value).toBe(false)
  })

  it('loads user from localStorage', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))

    // Re-import to get fresh state
    const { useAuth } = await import('../useAuth.js')
    const { user, isAuthenticated } = useAuth()

    expect(isAuthenticated.value).toBe(true)
    expect(user.value).toEqual({ email: 'test@example.com' })
  })

  it('login sets user on success (token is in HttpOnly cookie)', async () => {
    api.auth.login.mockResolvedValueOnce({
      ok: true,
      data: { access_token: 'new-token', token_type: 'bearer', role: 'user' }
    })

    const { login, isAuthenticated, user } = useAuth()

    const result = await login('test@example.com', 'password')

    expect(result.ok).toBe(true)
    // Token should NOT be stored in localStorage (it's in HttpOnly cookie)
    expect(localStorage.getItem('access_token')).toBeNull()
    // User info should be stored for UI purposes
    expect(isAuthenticated.value).toBe(true)
    expect(user.value).toEqual({ email: 'test@example.com', role: 'user' })
  })

  it('login does not set user on failure', async () => {
    // Clear localStorage to ensure clean state
    localStorage.clear()

    // Re-import to get fresh state
    const { useAuth } = await import('../useAuth.js')
    const { login, isAuthenticated, user } = useAuth()

    api.auth.login.mockResolvedValueOnce({
      ok: false,
      error: 'Invalid credentials'
    })

    const result = await login('test@example.com', 'wrong-password')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Invalid credentials')
    expect(isAuthenticated.value).toBe(false)
    expect(user.value).toBeNull()
  })

  it('logout clears user', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))

    api.auth.logout.mockResolvedValueOnce({ ok: true })

    const { logout, isAuthenticated, user } = useAuth()

    await logout()

    // Token should not be in localStorage (HttpOnly cookie)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(isAuthenticated.value).toBe(false)
    expect(user.value).toBeNull()
  })

  it('logout throws when API call fails', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))

    api.auth.logout.mockRejectedValueOnce(new Error('Network error'))

    const { logout } = useAuth()

    await expect(logout()).rejects.toThrow('Network error')
  })

  it('register calls api.auth.register', async () => {
    api.auth.register.mockResolvedValueOnce({
      ok: true,
      data: { id: 'user-1', email: 'new@example.com' }
    })

    const { register } = useAuth()

    const result = await register('new@example.com', 'password')

    expect(api.auth.register).toHaveBeenCalledWith('new@example.com', 'password')
    expect(result.ok).toBe(true)
  })

  it('register returns error on failure', async () => {
    api.auth.register.mockResolvedValueOnce({
      ok: false,
      error: 'Email already exists'
    })

    const { register } = useAuth()

    const result = await register('existing@example.com', 'password')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Email already exists')
  })

  it('getToken returns null (token is in HttpOnly cookie)', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))

    const { useAuth } = await import('../useAuth.js')
    const { getToken } = useAuth()

    // getToken is deprecated - returns null since token is in HttpOnly cookie
    expect(getToken()).toBeNull()
  })

  it('setAuth manually sets user', async () => {
    localStorage.clear()
    const { useAuth } = await import('../useAuth.js')
    const { setAuth, user, isAuthenticated } = useAuth()

    setAuth({ email: 'manual@example.com' })

    expect(isAuthenticated.value).toBe(true)
    expect(user.value).toEqual({ email: 'manual@example.com' })
    // Token should not be stored in localStorage
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('clearAuth clears user state', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))
    localStorage.setItem('user_role', 'admin')

    const { useAuth } = await import('../useAuth.js')
    const { clearAuth, user, isAuthenticated, isAdmin } = useAuth()

    clearAuth()

    expect(isAuthenticated.value).toBe(false)
    expect(user.value).toBeNull()
    expect(isAdmin.value).toBe(false)
    expect(localStorage.getItem('user')).toBeNull()
    expect(localStorage.getItem('user_role')).toBeNull()
  })
})
