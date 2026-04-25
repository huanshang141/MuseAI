import { describe, it, expect } from 'vitest'
import { BREAKPOINTS } from '../breakpoints.js'

describe('design-system breakpoints', () => {
  it('exports the 5 required breakpoints', () => {
    expect(BREAKPOINTS).toEqual({
      xs: 0,
      sm: 640,
      md: 768,
      lg: 1024,
      xl: 1280,
    })
  })
})
