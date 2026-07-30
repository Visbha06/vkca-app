import {
  useCallback,
  useEffect,
  useRef,
  type PointerEvent,
  type RefObject,
} from 'react'

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function getFocusableElements(dialog: HTMLElement) {
  return Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector))
}

export function useBackdropDismiss(onDismiss: () => void) {
  const onDismissRef = useRef(onDismiss)
  const pointerDownRef = useRef<{
    backdrop: EventTarget
    pointerId: number
  } | null>(null)

  useEffect(() => {
    onDismissRef.current = onDismiss
  }, [onDismiss])

  const resetPointer = useCallback(() => {
    pointerDownRef.current = null
  }, [])

  const onPointerDown = useCallback((event: PointerEvent<HTMLElement>) => {
    pointerDownRef.current =
      event.target === event.currentTarget
        ? {
            backdrop: event.currentTarget,
            pointerId: event.pointerId,
          }
        : null
  }, [])

  const onPointerUp = useCallback((event: PointerEvent<HTMLElement>) => {
    const pointerDown = pointerDownRef.current
    pointerDownRef.current = null
    if (
      pointerDown?.backdrop === event.currentTarget &&
      pointerDown.pointerId === event.pointerId &&
      event.target === event.currentTarget
    ) {
      onDismissRef.current()
    }
  }, [])

  useEffect(() => resetPointer, [resetPointer])

  return {
    onPointerCancel: resetPointer,
    onPointerDown,
    onPointerUp,
  }
}

export function useModalDialog(
  dialogRef: RefObject<HTMLDivElement | null>,
  onClose: () => void,
) {
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog === null) return
    const activeDialog: HTMLDivElement = dialog

    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const initialFocus = activeDialog.querySelector<HTMLElement>(
      '[data-modal-initial-focus]',
    )
    initialFocus?.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }

      if (event.key !== 'Tab') return
      const focusableElements = getFocusableElements(activeDialog)
      if (focusableElements.length === 0) return

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]
      const activeElement = document.activeElement

      if (
        event.shiftKey &&
        (activeElement === firstElement || !activeDialog.contains(activeElement))
      ) {
        event.preventDefault()
        lastElement.focus()
      } else if (
        !event.shiftKey &&
        (activeElement === lastElement || !activeDialog.contains(activeElement))
      ) {
        event.preventDefault()
        firstElement.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [dialogRef])
}
