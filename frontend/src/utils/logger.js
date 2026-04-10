/**
 * Environment-gated logger for development-only debug output.
 * In production builds, all debug logging is suppressed to prevent
 * sensitive data leakage (credentials, tokens, request/response bodies).
 */

const SENSITIVE_PARAMS = ['token', 'key', 'secret', 'password', 'api_key', 'access_token']

function sanitizeUrl(url) {
  try {
    const parsed = new URL(url, window.location.origin)
    for (const key of SENSITIVE_PARAMS) {
      if (parsed.searchParams.has(key)) {
        parsed.searchParams.set(key, '[REDACTED]')
      }
    }
    return parsed.toString()
  } catch {
    return '[invalid-url]'
  }
}

function sanitizeArgs(args) {
  if (!import.meta.env.PROD) return args
  return args.map(arg => {
    if (typeof arg === 'string' && arg.startsWith('http')) {
      return sanitizeUrl(arg)
    }
    return arg
  })
}

export function debug(...args) {
  if (import.meta.env.DEV) {
    console.debug(...args)
  }
}

export function log(...args) {
  if (import.meta.env.DEV) {
    console.log(...args)
  }
}

export function warn(...args) {
  if (import.meta.env.DEV) {
    console.warn(...args)
  }
}

export function error(...args) {
  if (import.meta.env.PROD) {
    console.error(...sanitizeArgs(args))
  } else {
    console.error(...args)
  }
}
