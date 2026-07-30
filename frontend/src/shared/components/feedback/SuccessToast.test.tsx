// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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

    vi.advanceTimersByTime(4499)
    expect(onDismiss).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
