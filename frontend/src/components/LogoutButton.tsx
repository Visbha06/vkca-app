import { useAuth } from '../auth/AuthContext'

export default function LogoutButton() {
  const { isLogoutPending, logout } = useAuth()

  return (
    <button
      type="button"
      aria-busy={isLogoutPending}
      aria-label="Log out"
      className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-red-600 text-white transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 focus:ring-offset-slate-900 active:bg-red-800 disabled:cursor-wait disabled:opacity-70"
      data-mobile-drawer-focus
      disabled={isLogoutPending}
      onClick={() => void logout()}
      title="Log out"
    >
      <svg
        aria-hidden="true"
        className="size-6"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
      >
        <path d="M10 5H5v14h5" />
        <path d="M14 8l4 4-4 4M18 12H9" />
      </svg>
    </button>
  )
}
