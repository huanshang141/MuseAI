import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../../api/index.js'

describe('LLMTraceManager API client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('calls /admin/llm-traces for list', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.admin.llmTraces.list()

    expect(result.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalled()
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/admin/llm-traces')
  })

  it('calls /admin/llm-traces/:callId for detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ call_id: 'call-1', status: 'success' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.admin.llmTraces.get('call-1')

    expect(result.ok).toBe(true)
    expect(fetchMock).toHaveBeenCalled()
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/admin/llm-traces/call-1')
  })

  it('passes filter params for list', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await api.admin.llmTraces.list({ source: 'chat_stream', status: 'error' })

    const url = fetchMock.mock.calls[0][0]
    expect(url).toContain('source=chat_stream')
    expect(url).toContain('status=error')
  })

  it('handles error response gracefully', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal Server Error' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.admin.llmTraces.list()

    expect(result.ok).toBe(false)
    expect(result.status).toBe(500)
  })
})
