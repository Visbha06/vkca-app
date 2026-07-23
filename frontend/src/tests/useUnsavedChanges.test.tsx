// @vitest-environment jsdom

import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  UNSAVED_CHANGES_MESSAGE,
  useUnsavedChanges,
} from '../hooks/useUnsavedChanges'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('useUnsavedChanges', () => {
  it('closes immediately when the form is clean', () => {
    const onClose = vi.fn()
    const confirm = vi.spyOn(window, 'confirm')
    const { result } = renderHook(() => useUnsavedChanges(false, onClose))

    act(() => expect(result.current()).toBe(true))

    expect(confirm).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes a dirty form only after confirmation', () => {
    const onClose = vi.fn()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { result } = renderHook(() => useUnsavedChanges(true, onClose))

    act(() => expect(result.current()).toBe(true))

    expect(confirm).toHaveBeenCalledWith(UNSAVED_CHANGES_MESSAGE)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('keeps a dirty form open when discard is cancelled', () => {
    const onClose = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { result } = renderHook(() => useUnsavedChanges(true, onClose))

    act(() => expect(result.current()).toBe(false))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('protects dirty forms from browser-level navigation', () => {
    const { unmount } = renderHook(() => useUnsavedChanges(true, vi.fn()))
    const event = new Event('beforeunload', { cancelable: true })

    window.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(true)
    unmount()

    const cleanEvent = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(cleanEvent)
    expect(cleanEvent.defaultPrevented).toBe(false)
  })
})
