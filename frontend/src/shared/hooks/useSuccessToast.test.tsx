// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SuccessToast from '../components/feedback/SuccessToast'
import useSuccessToast from './useSuccessToast'

function SuccessToastHarness() {
  const {
    dismissSuccessToast,
    showSuccessToast,
    successToast,
  } = useSuccessToast()

  return (
    <>
      <button
        type="button"
        onClick={() => showSuccessToast('Saved successfully.')}
      >
        Show success
      </button>
      {successToast ? (
        <SuccessToast
          key={successToast.id}
          message={successToast.message}
          onDismiss={dismissSuccessToast}
        />
      ) : null}
    </>
  )
}

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('useSuccessToast', () => {
  it('clears dismissed state and does not restore it after rerender', () => {
    const view = render(<SuccessToastHarness />)
    fireEvent.click(screen.getByRole('button', { name: 'Show success' }))
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    view.rerender(<SuccessToastHarness />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('clears state automatically and restarts the timer for repeated events', () => {
    vi.useFakeTimers()
    render(<SuccessToastHarness />)
    const showSuccess = screen.getByRole('button', { name: 'Show success' })

    fireEvent.click(showSuccess)
    act(() => vi.advanceTimersByTime(4000))
    fireEvent.click(showSuccess)

    expect(screen.getAllByRole('status')).toHaveLength(1)
    act(() => vi.advanceTimersByTime(1000))
    expect(screen.getByRole('status')).toBeVisible()
    act(() => vi.advanceTimersByTime(3500))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
