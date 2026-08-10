// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DataQualityFinding } from '../api/dataQualityApi'
import DataQualityRemediationDialog from './DataQualityRemediationDialog'

const finding: DataQualityFinding = {
  finding_id: 'coach.inactive_assigned:coach:team',
  rule_id: 'coach.inactive_assigned',
  severity: 'warning',
  domain: 'coaches',
  entity_type: 'coach_assignment',
  entity_id: 'coach',
  entity_label: 'Alex Morgan — U13 Falcons',
  title: 'Inactive Assistant Coach remains assigned',
  explanation: 'The inactive assignment remains current.',
  recommended_action: 'Remove this one assignment.',
  direct_remediation: {
    action: 'remove_inactive_assistant_assignment',
    coach_id: 'coach',
    team_id: 'team',
    expected_coach_version: 4,
    confirmation_required: true,
  },
  related_entities: [],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DataQualityRemediationDialog', () => {
  it('names the exact relationship and restores keyboard-safe cancellation', () => {
    const onClose = vi.fn()
    render(
      <DataQualityRemediationDialog
        finding={finding}
        isSubmitting={false}
        onClose={onClose}
        onConfirm={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('dialog', {
        name: 'Remove inactive Assistant Coach assignment?',
      }),
    ).toBeVisible()
    expect(screen.getByText(/Alex Morgan — U13 Falcons/)).toBeVisible()
    expect(screen.getByText(/Only this one team assignment/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('disables dismissal and announces the submitting state', () => {
    const onClose = vi.fn()
    const onConfirm = vi.fn()
    render(
      <DataQualityRemediationDialog
        finding={finding}
        isSubmitting
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    )

    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Removing assignment…' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(
      'Applying the confirmed remediation',
    )

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
    expect(onConfirm).not.toHaveBeenCalled()
  })
})
