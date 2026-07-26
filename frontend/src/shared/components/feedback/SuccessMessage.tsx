import type { ReactNode } from 'react'

export default function SuccessMessage({ children }: { children: ReactNode }) {
  return (
    <p
      role="status"
      className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-950"
    >
      {children}
    </p>
  )
}
