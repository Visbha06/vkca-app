// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'

afterEach(cleanup)

function renderResponsiveLayout() {
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<h1>Home page</h1>} />
          <Route path="teams" element={<h1>Teams page</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('responsive navigation', () => {
  it('opens the mobile overlay from the navigation toggle', () => {
    renderResponsiveLayout()

    const sidebar = screen.getByLabelText('Application sidebar')
    const backdrop = screen.getByTestId('mobile-navigation-backdrop')

    expect(sidebar).toHaveAttribute('data-mobile-open', 'false')
    expect(backdrop).toHaveAttribute('data-open', 'false')

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation menu' }))

    expect(sidebar).toHaveAttribute('data-mobile-open', 'true')
    expect(backdrop).toHaveAttribute('data-open', 'true')
    expect(
      screen.getByRole('button', { name: 'Close navigation menu' }),
    ).toHaveAttribute('aria-expanded', 'true')
  })

  it('closes the mobile overlay when a navigation link is selected', async () => {
    renderResponsiveLayout()

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation menu' }))
    fireEvent.click(screen.getByRole('link', { name: 'Teams' }))

    expect(
      await screen.findByRole('heading', { name: 'Teams page' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Application sidebar')).toHaveAttribute(
      'data-mobile-open',
      'false',
    )
    expect(screen.getByTestId('mobile-navigation-backdrop')).toHaveAttribute(
      'data-open',
      'false',
    )
  })

  it('closes the mobile overlay from the backdrop or Escape key', () => {
    renderResponsiveLayout()

    const openNavigation = () =>
      fireEvent.click(
        screen.getByRole('button', { name: 'Open navigation menu' }),
      )
    const sidebar = screen.getByLabelText('Application sidebar')
    const backdrop = screen.getByTestId('mobile-navigation-backdrop')

    openNavigation()
    fireEvent.click(backdrop)
    expect(sidebar).toHaveAttribute('data-mobile-open', 'false')

    openNavigation()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(sidebar).toHaveAttribute('data-mobile-open', 'false')
  })

  it('exposes accessible navigation state and visible focus styles', () => {
    renderResponsiveLayout()

    const mobileToggle = screen.getByRole('button', {
      name: 'Open navigation menu',
    })
    const homeLink = screen.getByRole('link', { name: 'Home' })

    expect(mobileToggle).toHaveAttribute('aria-controls', 'application-sidebar')
    expect(mobileToggle).toHaveAttribute('aria-expanded', 'false')
    expect(mobileToggle).toHaveClass('focus:ring-2', 'focus:ring-academy')
    expect(homeLink).toHaveAttribute('aria-current', 'page')
    expect(homeLink).toHaveClass('focus:ring-2', 'focus:ring-academy')
    expect(
      screen.getByRole('navigation', { name: 'Primary navigation' }),
    ).toBeInTheDocument()
  })
})
