import { describe, expect, it } from 'vitest'
import router from '../index.js'

describe('not found route', () => {
  it('contains catch-all path', () => {
    const hit = router.getRoutes().find((route) => route.path === '/:pathMatch(.*)*')
    expect(hit).toBeTruthy()
  })
})
