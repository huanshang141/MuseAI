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
    localStorage.setItem('user', JSON.stringify({ email: 'x@y.com' }))
    localStorage.setItem('user_role', 'admin')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Unauthorized' }),
    }))

    await api.ready()

    // Note: access_token is no longer stored in localStorage since auth
    // now uses HttpOnly cookies. Only user metadata is cleared.
    expect(localStorage.getItem('user')).toBeNull()
    expect(localStorage.getItem('user_role')).toBeNull()
  })

  it('retries idempotent health request once after transient failure', async () => {
    vi.useFakeTimers()

    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ status: 'ok' }) })

    vi.stubGlobal('fetch', fetchMock)

    const pending = api.health()
    await vi.runAllTimersAsync()
    const result = await pending

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(result.ok).toBe(true)
  })

  it('verifies logger is called during api requests', async () => {
    // Mock the logger module to verify it's being called
    const loggerMock = {
      log: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    }

    vi.doMock('../../utils/logger.js', () => loggerMock)

    // Re-import api to get the mocked logger
    const { api: apiMocked } = await import('../index.js?logger-test')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'ok' }) }))

    await apiMocked.health()

    // Logger.log should be called for request logging
    expect(loggerMock.log).toHaveBeenCalled()

    vi.doUnmock('../../utils/logger.js')
  })
})
