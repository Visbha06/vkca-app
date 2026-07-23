// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import HomePage from '../pages/HomePage'

afterEach(cleanup)

function renderHomePage() {
  render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  )
}

describe('HomePage', () => {
  it('renders a personal academy dashboard introduction', () => {
    renderHomePage()

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'Good evening, Coach',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Here’s what’s happening at the academy.'),
    ).toBeInTheDocument()
  })

  it('shows the academy summary, events, and recent activity', () => {
    renderHomePage()

    const summary = screen.getByRole('region', { name: 'Academy summary' })
    expect(
      within(summary).getByRole('heading', { name: 'Upcoming training' }),
    ).toBeInTheDocument()
    expect(
      within(summary).getByRole('heading', { name: 'Next match' }),
    ).toBeInTheDocument()
    expect(
      within(summary).getByRole('heading', { name: 'Active players' }),
    ).toBeInTheDocument()
    expect(within(summary).getByText('84')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Upcoming events' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Recent academy activity' }),
    ).toBeInTheDocument()
  })

  it('offers the approved quick actions', () => {
    renderHomePage()

    const actions = screen.getByRole('navigation', { name: 'Quick actions' })
    expect(within(actions).getByRole('link', { name: 'Add player' })).toHaveAttribute(
      'href',
      '/players?action=add',
    )
    expect(within(actions).getByRole('link', { name: 'Create match' })).toHaveAttribute(
      'href',
      '/teams',
    )
    expect(
      within(actions).getByRole('link', { name: 'Schedule event' }),
    ).toHaveAttribute('href', '/calendar')
  })
})
