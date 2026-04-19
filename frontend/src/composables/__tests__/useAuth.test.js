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

  it('login sets user and token on success', async () => {
    api.auth.login.mockResolvedValueOnce({
      ok: true,
      data: { access_token: 'new-token', token_type: 'bearer', role: 'user' }
    })

    const { login, isAuthenticated, user } = useAuth()

    const result = await login('test@example.com', 'password')

    expect(result.ok).toBe(true)
    expect(localStorage.getItem('auth_token')).toBe('new-token')
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

  it('logout clears user and token', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))
    localStorage.setItem('auth_token', 'some-token')

    api.auth.logout.mockResolvedValueOnce({ ok: true })

    const { logout, isAuthenticated, user } = useAuth()

    await logout()

    expect(localStorage.getItem('auth_token')).toBeNull()
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

  it('getToken returns stored auth token', async () => {
    localStorage.setItem('auth_token', 'my-token')
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))

    const { useAuth } = await import('../useAuth.js')
    const { getToken } = useAuth()

    expect(getToken()).toBe('my-token')
  })

  it('setAuth manually sets user and token', async () => {
    localStorage.clear()
    const { useAuth } = await import('../useAuth.js')
    const { setAuth, user, isAuthenticated } = useAuth()

    setAuth({ email: 'manual@example.com' }, 'user', 'manual-token')

    expect(isAuthenticated.value).toBe(true)
    expect(user.value).toEqual({ email: 'manual@example.com' })
    expect(localStorage.getItem('auth_token')).toBe('manual-token')
  })

  it('clearAuth clears user state', async () => {
    localStorage.setItem('user', JSON.stringify({ email: 'test@example.com' }))
    localStorage.setItem('user_role', 'admin')
    localStorage.setItem('auth_token', 'some-token')

    const { useAuth } = await import('../useAuth.js')
    const { clearAuth, user, isAuthenticated, isAdmin } = useAuth()

    clearAuth()

    expect(isAuthenticated.value).toBe(false)
    expect(user.value).toBeNull()
    expect(isAdmin.value).toBe(false)
    expect(localStorage.getItem('user')).toBeNull()
    expect(localStorage.getItem('user_role')).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})
