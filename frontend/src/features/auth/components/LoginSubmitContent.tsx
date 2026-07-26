export default function LoginSubmitContent({ pending }: { pending: boolean }) {
  if (!pending) return 'Log in'

  return (
    <>
      <svg aria-hidden="true" className="mr-2 size-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" />
        <path className="opacity-75" d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeLinecap="round" strokeWidth="3" />
      </svg>
      Logging in
      <span className="sr-only" role="status">Signing in…</span>
    </>
  )
}
