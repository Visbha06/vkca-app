// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import HomePage from '../pages/HomePage'

afterEach(cleanup)

describe('HomePage', () => {
  it('renders the academy logo with descriptive alternative text', () => {
    render(<HomePage />)

    expect(
      screen.getByRole('img', { name: 'VK Cricket Academy logo' }),
    ).toBeInTheDocument()
  })

  it('renders the welcome title as a level-one heading', () => {
    render(<HomePage />)

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'Welcome to VK Cricket Academy!',
      }),
    ).toBeInTheDocument()
  })
})
