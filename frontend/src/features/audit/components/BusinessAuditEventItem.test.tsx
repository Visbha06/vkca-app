// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type {
  BusinessAuditActionType,
  BusinessAuditEvent,
  SafeBusinessAuditMetadata,
} from '../types/businessAudit'
import BusinessAuditEventItem from './BusinessAuditEventItem'

afterEach(cleanup)

const playerAccountEvents: Array<{
  action: Extract<
    BusinessAuditActionType,
    | 'player.account_linked'
    | 'player.account_unlinked'
    | 'player.account_reassigned'
  >
  metadata: SafeBusinessAuditMetadata
  expectedValues: string[]
}> = [
  {
    action: 'player.account_linked',
    metadata: { account_user_id: 'account-2' },
    expectedValues: ['account-2'],
  },
  {
    action: 'player.account_unlinked',
    metadata: { previous_account_user_id: 'account-1' },
    expectedValues: ['account-1'],
  },
  {
    action: 'player.account_reassigned',
    metadata: {
      previous_account_user_id: 'account-1',
      account_user_id: 'account-2',
    },
    expectedValues: ['account-1', 'account-2'],
  },
]

describe('BusinessAuditEventItem player-account events', () => {
  it.each(playerAccountEvents)(
    'renders $action and its allowlisted metadata',
    ({ action, expectedValues, metadata }) => {
      const event: BusinessAuditEvent = {
        id: '00000000-0000-4000-8000-000000000001',
        actor_user_id: '00000000-0000-4000-8000-000000000002',
        actor_display_name: 'Asha Coach',
        actor_role: 'head coach',
        action_type: action,
        action_category: 'player',
        target_entity_type: 'player',
        target_entity_id: '00000000-0000-4000-8000-000000000003',
        target_label: 'Rohan Player',
        summary: `Account event: ${action}`,
        metadata,
        created_at: '2026-08-10T18:00:00Z',
        request_id: null,
      }

      render(<BusinessAuditEventItem event={event} />)
      expect(screen.getByText(`Account event: ${action}`)).toBeVisible()
      fireEvent.click(
        screen.getByRole('button', { name: 'Show safe details' }),
      )
      for (const value of expectedValues) {
        expect(screen.getByText(value)).toBeVisible()
      }
    },
  )
})
