import { describe, it, expect } from 'vitest'
import router from '../index.js'

describe('design-system route', () => {
  it('contains /design-system route', () => {
    const target = router.getRoutes().find((r) => r.path === '/design-system')
    expect(target).toBeTruthy()
  })
})
