// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { isAbortError } from './errors'

describe('isAbortError', () => {
  it('recognizes only AbortError DOM exceptions', () => {
    expect(isAbortError(new DOMException('aborted', 'AbortError'))).toBe(true)
    expect(isAbortError(new DOMException('failed', 'NetworkError'))).toBe(false)
    expect(isAbortError(new Error('AbortError'))).toBe(false)
    expect(isAbortError(null)).toBe(false)
  })
})
