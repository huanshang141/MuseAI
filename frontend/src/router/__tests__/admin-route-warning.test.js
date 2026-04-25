import { describe, expect, it, vi } from 'vitest'

describe('admin route warning', () => {
  it('does not warn when admin route has an empty-path child', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    await import('../index.js?admin-route-warning')

    const hasWarning = warnSpy.mock.calls.some(([message]) =>
      String(message).includes(
        'The route named "admin" has a child without a name and an empty path'
      )
    )

    expect(hasWarning).toBe(false)

    warnSpy.mockRestore()
  })
})
