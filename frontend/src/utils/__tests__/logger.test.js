import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'

// We need to mock import.meta.env.DEV which is a compile-time constant
// Vitest allows us to do this via vi.stubGlobal on import.meta or using define
// in vitest config. For unit testing the logger module directly, we can
// use module mocking with vi.mock and manually control the DEV value.

describe('logger', () => {
  let consoleSpies

  beforeEach(() => {
    // Capture all console methods before each test
    consoleSpies = {
      debug: vi.spyOn(console, 'debug').mockImplementation(() => {}),
      log: vi.spyOn(console, 'log').mockImplementation(() => {}),
      warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
      error: vi.spyOn(console, 'error').mockImplementation(() => {}),
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.resetModules()
  })

  describe('in development mode (DEV = true)', () => {
    it('calls console.debug when debug() is invoked', async () => {
      // Set DEV to true and re-import the module
      vi.stubGlobal('import.meta', { env: { DEV: true } })

      // Re-import to pick up the mocked environment
      const { debug } = await import('../logger.js?dev-test-true')

      debug('test debug message')

      expect(consoleSpies.debug).toHaveBeenCalledWith('test debug message')
    })

    it('calls console.log when log() is invoked', async () => {
      vi.stubGlobal('import.meta', { env: { DEV: true } })

      const { log } = await import('../logger.js?log-test-true')

      log('test log message')

      expect(consoleSpies.log).toHaveBeenCalledWith('test log message')
    })

    it('calls console.warn when warn() is invoked', async () => {
      vi.stubGlobal('import.meta', { env: { DEV: true } })

      const { warn } = await import('../logger.js?warn-test-true')

      warn('test warn message')

      expect(consoleSpies.warn).toHaveBeenCalledWith('test warn message')
    })

    it('always calls console.error when error() is invoked', async () => {
      vi.stubGlobal('import.meta', { env: { DEV: true } })

      const { error } = await import('../logger.js?error-test-true')

      error('test error message')

      expect(consoleSpies.error).toHaveBeenCalledWith('test error message')
    })
  })

  describe('in production mode (DEV = false)', () => {
    it('does NOT call console.debug when debug() is invoked', async () => {
      // Note: import.meta.env.DEV is replaced at build time by Vite
      // In Vitest, we can use vi.stubEnv which actually works for Vite env vars
      vi.stubEnv('DEV', false)

      const { debug } = await import('../logger.js?prod-test-debug')

      debug('test debug message')

      expect(consoleSpies.debug).not.toHaveBeenCalled()
    })

    it('does NOT call console.log when log() is invoked', async () => {
      vi.stubEnv('DEV', false)

      const { log } = await import('../logger.js?prod-test-log')

      log('test log message')

      expect(consoleSpies.log).not.toHaveBeenCalled()
    })

    it('does NOT call console.warn when warn() is invoked', async () => {
      vi.stubEnv('DEV', false)

      const { warn } = await import('../logger.js?prod-test-warn')

      warn('test warn message')

      expect(consoleSpies.warn).not.toHaveBeenCalled()
    })

    it('STILL calls console.error when error() is invoked (errors always logged)', async () => {
      vi.stubEnv('DEV', false)

      const { error } = await import('../logger.js?prod-test-error')

      error('test error message')

      // Error logging should always happen, even in production
      expect(consoleSpies.error).toHaveBeenCalledWith('test error message')
    })
  })
})
