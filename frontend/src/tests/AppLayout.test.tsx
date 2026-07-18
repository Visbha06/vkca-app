// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'
import { useSidebar } from '../layouts/SidebarContext'

afterEach(cleanup)

function ContextProbe() {
  const { expanded, mobileOpen } = useSidebar()

  return (
    <p>
      Sidebar context: {expanded ? 'expanded' : 'collapsed'},{' '}
      {mobileOpen ? 'open' : 'closed'}
    </p>
  )
}

function renderLayout(child = <h1>Test content</h1>) {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={child} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AppLayout', () => {
  it('renders the application sidebar and main content area', () => {
    renderLayout()

    expect(screen.getByLabelText('Application sidebar')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Primary navigation' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toContainElement(
      screen.getByRole('heading', { name: 'Test content' }),
    )
  })

  it('provides the default sidebar state to routed content', () => {
    renderLayout(<ContextProbe />)

    expect(
      screen.getByText('Sidebar context: expanded, closed'),
    ).toBeInTheDocument()
  })
})
