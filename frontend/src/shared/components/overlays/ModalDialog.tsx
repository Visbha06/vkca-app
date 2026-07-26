import {
  useEffect,
  useRef,
  type MouseEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

interface ModalDialogProps {
  children: ReactNode
  labelledBy: string
  onClose: () => void
  testId?: string
}

export default function ModalDialog({
  children,
  labelledBy,
  onClose,
  testId,
}: ModalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog === null) return
    const activeDialog: HTMLDialogElement = dialog

    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    const supportsModal = typeof activeDialog.showModal === 'function'
    document.body.style.overflow = 'hidden'

    if (supportsModal) {
      activeDialog.showModal()
    } else {
      activeDialog.setAttribute('open', '')
    }

    activeDialog
      .querySelector<HTMLElement>('[data-modal-initial-focus]')
      ?.focus()

    function handleCancel(event: Event) {
      event.preventDefault()
      onCloseRef.current()
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (!supportsModal && event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return

      const focusable = Array.from(
        activeDialog.querySelectorAll<HTMLElement>(focusableSelector),
      ).filter((element) => element.closest('[inert]') === null)
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      if (
        event.shiftKey &&
        (active === first || !activeDialog.contains(active))
      ) {
        event.preventDefault()
        last.focus()
      } else if (
        !event.shiftKey &&
        (active === last || !activeDialog.contains(active))
      ) {
        event.preventDefault()
        first.focus()
      }
    }

    activeDialog.addEventListener('cancel', handleCancel)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      activeDialog.removeEventListener('cancel', handleCancel)
      document.removeEventListener('keydown', handleKeyDown)
      if (
        activeDialog.open &&
        typeof activeDialog.close === 'function'
      ) {
        activeDialog.close()
      }
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [])

  function handleBackdropClick(event: MouseEvent<HTMLDialogElement>) {
    if (event.target === event.currentTarget) onClose()
  }

  if (typeof document === 'undefined') return null

  return createPortal(
    <dialog
      ref={dialogRef}
      aria-labelledby={labelledBy}
      aria-modal="true"
      className="modal-dialog"
      data-testid={testId}
      onClick={handleBackdropClick}
    >
      {children}
    </dialog>,
    document.body,
  )
}
