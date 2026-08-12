import type { FormEvent } from 'react'
import type { PlayerAccountSnapshot } from '../../types/player'
import type { PlayerAccountDialogMode } from './usePlayerAccountDialog'

interface ContentProps {
  accounts: PlayerAccountSnapshot[]
  errorMessage: string | null
  hasConflict: boolean
  isLoading: boolean
  isSubmitting: boolean
  mode: PlayerAccountDialogMode
  search: string
  selectedId: string | null
  onCancel: () => void
  onConflict: () => void
  onSearch: () => void
  onSearchChange: (value: string) => void
  onSelect: (accountId: string) => void
  onSubmit: () => void
}

const modeCopy = {
  link: {
    title: 'Link player account',
    description: 'Choose the exact Player-role account, then confirm the association.',
    action: 'Link selected account',
  },
  reassign: {
    title: 'Reassign player account',
    description: 'Choose the correct replacement account and confirm this correction.',
    action: 'Reassign selected account',
  },
  unlink: {
    title: 'Unlink player account',
    description: 'The Player profile and login account will remain. Only their association will be removed.',
    action: 'Unlink account',
  },
} as const

export default function PlayerAccountDialogContent(props: ContentProps) {
  const copy = modeCopy[props.mode]
  function submit(event: FormEvent) {
    event.preventDefault()
    props.onSubmit()
  }

  return (
    <form onSubmit={submit} className="p-5 sm:p-6">
      <header className="pr-12">
        <h2 id="player-account-dialog-title" className="text-xl font-bold text-slate-900">
          {copy.title}
        </h2>
        <p id="player-account-dialog-description" className="mt-2 max-w-prose text-sm leading-6 text-slate-700">
          {copy.description}
        </p>
      </header>

      {props.mode !== 'unlink' ? (
        <div className="mt-6">
          <label htmlFor="player-account-search" className="text-sm font-semibold text-slate-800">
            Search player accounts
          </label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <input
              id="player-account-search"
              type="search"
              value={props.search}
              onChange={(event) => props.onSearchChange(event.target.value)}
              className="min-h-11 min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-slate-900 outline-none focus:border-academy focus:ring-2 focus:ring-academy/40"
            />
            <button type="button" onClick={props.onSearch} className="min-h-11 rounded-lg border border-academy bg-white px-4 text-sm font-semibold text-slate-900 hover:bg-academy/10 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">
              Search
            </button>
          </div>
          {props.isLoading ? (
            <p role="status" className="mt-4 text-sm text-slate-700">Loading eligible accounts…</p>
          ) : props.accounts.length === 0 ? (
            <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">No eligible unlinked Player accounts found.</p>
          ) : (
            <fieldset className="mt-4 space-y-2">
              <legend className="sr-only">Eligible Player accounts</legend>
              {props.accounts.map((account) => (
                <label key={account.id} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:border-academy hover:bg-academy/10">
                  <input type="radio" name="player-account" value={account.id} checked={props.selectedId === account.id} onChange={() => props.onSelect(account.id)} className="mt-1 size-4 accent-slate-900" />
                  <span className="min-w-0">
                    <span className="block font-semibold text-slate-900">{account.display_name}</span>
                    <span className="block break-words text-sm text-slate-700">{account.email}</span>
                    {!account.is_active ? <span className="mt-1 block text-sm font-semibold text-amber-900">Account inactive</span> : null}
                  </span>
                </label>
              ))}
            </fieldset>
          )}
        </div>
      ) : null}

      {props.errorMessage !== null ? (
        <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-950">
          <p>{props.errorMessage}</p>
          {props.hasConflict ? (
            <button type="button" onClick={props.onConflict} className="mt-3 min-h-11 rounded-lg border border-red-800 bg-white px-4 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2">Reload latest account link</button>
          ) : null}
        </div>
      ) : null}

      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button type="button" onClick={props.onCancel} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2">Cancel</button>
        <button type="submit" disabled={props.hasConflict || props.isSubmitting || (props.mode !== 'unlink' && props.selectedId === null)} className={`${props.mode === 'unlink' ? 'bg-red-800 hover:bg-red-900 focus:ring-red-800' : 'bg-slate-900 hover:bg-slate-800 focus:ring-academy'} min-h-11 rounded-lg px-4 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400`}>
          {props.isSubmitting ? 'Saving account link…' : copy.action}
        </button>
      </div>
    </form>
  )
}
