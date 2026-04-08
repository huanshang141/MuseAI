/**
 * Environment-gated logger for development-only debug output.
 * In production builds, all debug logging is suppressed to prevent
 * sensitive data leakage (credentials, tokens, request/response bodies).
 */

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
  // Errors are always logged, but consider removing in production
  // if they contain sensitive information
  console.error(...args)
}