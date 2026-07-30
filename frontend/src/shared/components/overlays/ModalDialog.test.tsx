// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ModalDialog from './ModalDialog'

function renderModal(onClose = vi.fn()) {
  render(
    <ModalDialog
      labelledBy="shared-modal-title"
      onClose={onClose}
      testId="shared-modal-backdrop"
    >
      <section data-testid="shared-modal-content">
        <h2 id="shared-modal-title">Shared modal</h2>
        <button type="button" onClick={onClose}>
          Close modal
        </button>
      </section>
    </ModalDialog>,
  )
  return {
    backdrop: screen.getByTestId('shared-modal-backdrop'),
    content: screen.getByTestId('shared-modal-content'),
    onClose,
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ModalDialog backdrop dismissal', () => {
  it('closes when pointer-down and pointer-up both occur on the backdrop', () => {
    const { backdrop, onClose } = renderModal()

    fireEvent.pointerDown(backdrop, { pointerId: 1 })
    fireEvent.pointerUp(backdrop, { pointerId: 1 })

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('does not close when pointer-down begins inside and ends on the backdrop', () => {
    const { backdrop, content, onClose } = renderModal()

    fireEvent.pointerDown(content, { pointerId: 2 })
    fireEvent.pointerUp(backdrop, { pointerId: 2 })

    expect(onClose).not.toHaveBeenCalled()
  })

  it('does not close when pointer-down begins on the backdrop and ends inside', () => {
    const { backdrop, content, onClose } = renderModal()

    fireEvent.pointerDown(backdrop, { pointerId: 3 })
    fireEvent.pointerUp(content, { pointerId: 3 })

    expect(onClose).not.toHaveBeenCalled()
  })

  it('does not close when content is clicked', () => {
    const { content, onClose } = renderModal()

    fireEvent.click(content)

    expect(onClose).not.toHaveBeenCalled()
  })

  it('still closes from Escape', () => {
    const { onClose } = renderModal()

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('still closes from an explicit close button', () => {
    const { onClose } = renderModal()

    fireEvent.click(screen.getByRole('button', { name: 'Close modal' }))

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('resets the interaction without closing after pointer-cancel', () => {
    const { backdrop, onClose } = renderModal()

    fireEvent.pointerDown(backdrop, { pointerId: 4 })
    fireEvent.pointerCancel(backdrop, { pointerId: 4 })
    fireEvent.pointerUp(backdrop, { pointerId: 4 })

    expect(onClose).not.toHaveBeenCalled()
  })
})
