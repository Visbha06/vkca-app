// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SuccessToast from './SuccessToast'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('SuccessToast', () => {
  it('announces the message and supports manual dismissal', () => {
    const onDismiss = vi.fn()
    render(
      <SuccessToast
        message="Asst Coach is now inactive."
        onDismiss={onDismiss}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      'Asst Coach is now inactive.',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('automatically dismisses after the configured delay', () => {
    vi.useFakeTimers()
    const onDismiss = vi.fn()
    render(
      <SuccessToast
        message="Asst Coach is now active."
        onDismiss={onDismiss}
      />,
    )

    act(() => vi.advanceTimersByTime(4499))
    expect(onDismiss).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('pauses while hovered and resumes with the remaining delay', () => {
    vi.useFakeTimers()
    const onDismiss = vi.fn()
    render(
      <SuccessToast
        dismissDelay={1000}
        message="Player saved."
        onDismiss={onDismiss}
      />,
    )

    act(() => vi.advanceTimersByTime(400))
    fireEvent.mouseEnter(screen.getByRole('status'))
    act(() => vi.advanceTimersByTime(1000))
    expect(onDismiss).not.toHaveBeenCalled()

    fireEvent.mouseLeave(screen.getByRole('status'))
    act(() => vi.advanceTimersByTime(599))
    expect(onDismiss).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('remains paused while focus is within the toast', () => {
    vi.useFakeTimers()
    const onDismiss = vi.fn()
    render(
      <SuccessToast
        dismissDelay={1000}
        message="Team saved."
        onDismiss={onDismiss}
      />,
    )

    const status = screen.getByRole('status')
    const dismiss = screen.getByRole('button', { name: 'Dismiss' })
    act(() => vi.advanceTimersByTime(400))
    fireEvent.mouseEnter(status)
    act(() => dismiss.focus())
    fireEvent.mouseLeave(status)
    act(() => vi.advanceTimersByTime(1000))
    expect(onDismiss).not.toHaveBeenCalled()

    act(() => dismiss.blur())
    act(() => vi.advanceTimersByTime(599))
    expect(onDismiss).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
