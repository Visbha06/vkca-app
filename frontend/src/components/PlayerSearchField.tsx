import type { ChangeEvent, RefObject } from 'react'

interface PlayerSearchFieldProps {
  inputRef: RefObject<HTMLInputElement | null>
  value: string
  onChange: (value: string) => void
}

export default function PlayerSearchField({
  inputRef,
  value,
  onChange,
}: PlayerSearchFieldProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onChange(event.target.value)
  }

  return (
    <div className="min-w-0 flex-1">
      <label
        htmlFor="player-search"
        className="mb-2 block text-sm font-semibold text-slate-800"
      >
        Search players
      </label>
      <span className="relative block">
        <svg
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-slate-500"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            cx="11"
            cy="11"
            r="7"
            stroke="currentColor"
            strokeWidth="2"
          />
          <path
            d="m16 16 4 4"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="2"
          />
        </svg>
        <input
          ref={inputRef}
          id="player-search"
          type="search"
          autoComplete="off"
          className="min-h-11 w-full rounded-lg border border-slate-300 bg-white py-2 pl-10 pr-3 text-base text-slate-900 placeholder:text-slate-600 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40"
          placeholder="Search by player name"
          value={value}
          onChange={handleChange}
        />
      </span>
    </div>
  )
}
