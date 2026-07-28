import {
  useLayoutEffect,
  useState,
  type RefObject,
} from 'react'

export interface PopoverPosition {
  left: number
  top: number
}

interface UseAnchoredPopoverPositionOptions {
  isOpen: boolean
  layoutKey: string
  popoverRef: RefObject<HTMLDivElement | null>
  triggerRef: RefObject<HTMLButtonElement | null>
}

export function useAnchoredPopoverPosition({
  isOpen,
  layoutKey,
  popoverRef,
  triggerRef,
}: UseAnchoredPopoverPositionOptions) {
  const [position, setPosition] = useState<PopoverPosition>({
    left: 0,
    top: 0,
  })

  useLayoutEffect(() => {
    if (!isOpen) return

    function updatePosition() {
      const trigger = triggerRef.current
      const popover = popoverRef.current
      if (trigger === null || popover === null) return
      const triggerBounds = trigger.getBoundingClientRect()
      const popoverBounds = popover.getBoundingClientRect()
      const measuredSpacing = Number.parseFloat(
        getComputedStyle(document.documentElement)
          .getPropertyValue('--spacing'),
      )
      const spacing = Number.isFinite(measuredSpacing) ? measuredSpacing : 0
      const preferredMargin = spacing * 3
      const availableMargin = Math.max(
        0,
        (window.innerWidth - popoverBounds.width) / 2,
      )
      const margin = Math.min(preferredMargin, availableMargin)
      const left = Math.min(
        Math.max(triggerBounds.left, margin),
        window.innerWidth - popoverBounds.width - margin,
      )
      const below = window.innerHeight - triggerBounds.bottom - margin
      const above = triggerBounds.top - margin
      const preferredTop =
        popoverBounds.height <= below || below >= above
          ? triggerBounds.bottom + spacing
          : triggerBounds.top - popoverBounds.height - spacing
      setPosition({
        left: Math.max(margin, left),
        top: Math.max(
          margin,
          Math.min(
            preferredTop,
            window.innerHeight - popoverBounds.height - margin,
          ),
        ),
      })
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [isOpen, layoutKey, popoverRef, triggerRef])

  return position
}
