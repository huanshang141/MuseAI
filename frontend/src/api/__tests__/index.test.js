import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../index.js'

describe('api request hardening', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('returns normalized envelope on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const result = await api.health()

    expect(result.ok).toBe(false)
    expect(result.status).toBe(0)
    expect(result.data.detail).toContain('Failed to fetch')
  })

  it('clears auth storage on 401 response', async () => {
    localStorage.setItem('access_token', 'token')
    localStorage.setItem('user', JSON.stringify({ email: 'x@y.com' }))
    localStorage.setItem('user_role', 'admin')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized' }),
    }))

    await api.ready()

    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
    expect(localStorage.getItem('user_role')).toBeNull()
  })
})
