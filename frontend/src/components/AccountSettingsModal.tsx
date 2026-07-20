import { useRef, type MouseEvent } from 'react'
import AccountPasswordForm from './AccountPasswordForm'
import AccountProfileForm from './AccountProfileForm'
import { useModalDialog } from './useModalDialog'

interface AccountSettingsModalProps {
  onClose: () => void
}

export default function AccountSettingsModal({ onClose }: AccountSettingsModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  useModalDialog(dialogRef, onClose)

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-slate-900/60 p-3 sm:p-6"
      data-testid="account-settings-backdrop"
      onClick={handleBackdropClick}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-settings-title"
        aria-describedby="account-settings-description"
        className="relative max-h-full w-full max-w-2xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white text-slate-900"
      >
        <header className="border-b border-slate-200 p-5 pr-16 sm:p-6 sm:pr-16">
          <h1 id="account-settings-title" className="text-xl font-bold text-slate-900">
            User Settings
          </h1>
          <p id="account-settings-description" className="mt-1 max-w-prose text-sm leading-6 text-slate-600">
            Manage the account details used across VK Cricket Academy.
          </p>
        </header>

        <AccountProfileForm />
        <AccountPasswordForm />

        <button
          type="button"
          aria-label="Close account settings"
          className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 sm:right-4 sm:top-4"
          onClick={onClose}
        >
          <svg aria-hidden="true" className="size-6" fill="none" viewBox="0 0 24 24">
            <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
          </svg>
        </button>
      </div>
    </div>
  )
}
