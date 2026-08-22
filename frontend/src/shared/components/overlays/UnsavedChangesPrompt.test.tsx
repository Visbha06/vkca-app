// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ModalDialog from './ModalDialog'
import UnsavedChangesPrompt from './UnsavedChangesPrompt'

afterEach(cleanup)

function renderPrompt() {
  const onClose = vi.fn()
  const onContinueEditing = vi.fn()
  const onDiscard = vi.fn()
  render(
    <ModalDialog
      describedBy="test-unsaved-description"
      labelledBy="test-unsaved-title"
      onClose={onClose}
      role="alertdialog"
      testId="test-unsaved-dialog"
    >
      <UnsavedChangesPrompt
        title="Discard unsaved changes?"
        titleId="test-unsaved-title"
        description="Your edits will be removed."
        descriptionId="test-unsaved-description"
        onContinueEditing={onContinueEditing}
        onDiscard={onDiscard}
      />
    </ModalDialog>,
  )
  return { onClose, onContinueEditing, onDiscard }
}

describe('UnsavedChangesPrompt', () => {
  it('uses the dialog shell for alert semantics and focuses the safe action', () => {
    renderPrompt()

    const dialog = screen.getByRole('alertdialog', {
      name: 'Discard unsaved changes?',
      description: 'Your edits will be removed.',
    })
    expect(dialog).toBe(screen.getByTestId('test-unsaved-dialog'))
    expect(
      screen.getByRole('button', { name: 'Continue editing' }),
    ).toHaveFocus()
    expect(dialog.querySelector('[role="alertdialog"]')).toBeNull()
  })

  it('preserves prompt actions, Escape, and backdrop dismissal', () => {
    const { onClose, onContinueEditing, onDiscard } = renderPrompt()
    const dialog = screen.getByTestId('test-unsaved-dialog')

    fireEvent.click(screen.getByRole('button', { name: 'Continue editing' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }))
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.pointerDown(dialog, { pointerId: 1 })
    fireEvent.pointerUp(dialog, { pointerId: 1 })

    expect(onContinueEditing).toHaveBeenCalledOnce()
    expect(onDiscard).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
