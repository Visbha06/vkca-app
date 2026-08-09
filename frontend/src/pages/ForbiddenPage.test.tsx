// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import ForbiddenPage from './ForbiddenPage'

describe('ForbiddenPage', () => {
  it('preserves the Coaches Portal forbidden experience by default', () => {
    render(<MemoryRouter><ForbiddenPage /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: 'Coaches Portal is for coaches only.' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Return to Dashboard' })).toHaveAttribute('href', '/')
  })

  it('accepts feature-specific copy for the Audit Log route', () => {
    render(
      <MemoryRouter>
        <ForbiddenPage
          title="Audit Log is available to Head Coaches only."
          description="Your account does not have access to recorded academy activity."
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Audit Log is available to Head Coaches only.' })).toBeVisible()
    expect(screen.getByText('Your account does not have access to recorded academy activity.')).toBeVisible()
  })
})
