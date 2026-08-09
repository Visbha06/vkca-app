// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAnchoredPopoverPosition } from './useAnchoredPopoverPosition'

function rect({
  left,
  top,
  width,
  height,
}: {
  left: number
  top: number
  width: number
  height: number
}) {
  return {
    bottom: top + height,
    height,
    left,
    right: left + width,
    top,
    width,
    x: left,
    y: top,
    toJSON: () => undefined,
  }
}

function PositionHarness() {
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const position = useAnchoredPopoverPosition({
    isOpen: true,
    layoutKey: 'test',
    popoverRef,
    triggerRef,
  })

  return (
    <>
      <button
        ref={triggerRef}
        style={{ paddingInlineStart: '12px' }}
        type="button"
      >
        Date
      </button>
      <div ref={popoverRef} data-testid="popover" style={position} />
    </>
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('useAnchoredPopoverPosition', () => {
  it('resolves the token-based trigger padding to a pixel viewport gutter', () => {
    vi.stubGlobal('innerWidth', 1440)
    vi.stubGlobal('innerHeight', 900)
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
      function getBounds(this: HTMLElement) {
        return this.dataset.testid === 'popover'
          ? rect({ left: 0, top: 0, width: 320, height: 366 })
          : rect({ left: 1300, top: 100, width: 80, height: 44 })
      },
    )

    render(<PositionHarness />)

    expect(screen.getByTestId('popover')).toHaveStyle({
      left: '1108px',
      top: '148px',
    })
  })

  it('preserves the two-sided gutter when the popover fills a narrow viewport', () => {
    vi.stubGlobal('innerWidth', 320)
    vi.stubGlobal('innerHeight', 720)
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(
      function getBounds(this: HTMLElement) {
        return this.dataset.testid === 'popover'
          ? rect({ left: 0, top: 0, width: 296, height: 366 })
          : rect({ left: 16, top: 100, width: 272, height: 44 })
      },
    )

    render(<PositionHarness />)

    expect(screen.getByTestId('popover')).toHaveStyle({
      left: '12px',
      top: '148px',
    })
  })
})
