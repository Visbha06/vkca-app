// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PasswordInput from '../components/PasswordInput'

afterEach(cleanup)

describe('PasswordInput', () => {
  it('toggles visibility with an accessible native button', () => {
    const onChange = vi.fn()
    render(
      <PasswordInput
        id="new-password"
        label="New password"
        value="StrongPassword!1"
        onChange={onChange}
      />,
    )

    const input = screen.getByLabelText('New password')
    const toggle = screen.getByRole('button', { name: 'Show new password' })

    expect(input).toHaveAttribute('type', 'password')
    expect(toggle).toHaveAttribute('type', 'button')

    toggle.focus()
    expect(toggle).toHaveFocus()
    fireEvent.click(toggle)

    expect(input).toHaveAttribute('type', 'text')
    expect(
      screen.getByRole('button', { name: 'Hide new password' }),
    ).toHaveFocus()
  })

  it('associates field errors and forwards value changes', () => {
    const onChange = vi.fn()
    render(
      <PasswordInput
        id="new-password"
        label="New password"
        value=""
        errors={['Password must include an uppercase letter.']}
        onChange={onChange}
      />,
    )

    const input = screen.getByLabelText('New password')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription(
      'Password must include an uppercase letter.',
    )

    fireEvent.change(input, { target: { value: 'UpdatedPassword!1' } })
    expect(onChange).toHaveBeenCalledWith('UpdatedPassword!1')
  })
})
