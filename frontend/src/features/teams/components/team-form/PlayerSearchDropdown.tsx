import { useId, useLayoutEffect, useRef, useState, type ChangeEvent, type FocusEvent, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import usePlayerSearch from '../../hooks/usePlayerSearch'
import type { PlayerResponse } from '@features/players'
import type { TeamRosterSelection } from '../../types/team'

interface PlayerSearchDropdownProps {
  id: string
  label: string
  player: TeamRosterSelection | null
  excludedPlayerIds: string[]
  disabled?: boolean
  onChange: (player: TeamRosterSelection | null) => void
}

function playerName(player: TeamRosterSelection) {
  return `${player.first_name} ${player.last_name}`
}

function toSelection(player: PlayerResponse): TeamRosterSelection {
  return {
    player_id: player.id,
    first_name: player.first_name,
    last_name: player.last_name,
    is_active: player.is_active,
  }
}

export default function PlayerSearchDropdown({
  id,
  label,
  player,
  excludedPlayerIds,
  disabled = false,
  onChange,
}: PlayerSearchDropdownProps) {
  const listboxId = `${useId()}-options`
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState(player === null ? '' : playerName(player))
  const [isOpen, setIsOpen] = useState(false)
  const [portalHost, setPortalHost] = useState<HTMLElement | null>(null)
  const [position, setPosition] = useState({ left: 0, top: 0, width: 0 })
  const { errorMessage, isLoading, results, retry } = usePlayerSearch(
    query,
    isOpen,
    disabled,
  )

  useLayoutEffect(() => {
    if (!isOpen) return

    function positionDropdown() {
      const bounds = inputRef.current?.getBoundingClientRect()
      if (bounds === undefined) return
      setPosition({
        left: bounds.left,
        top: bounds.bottom,
        width: bounds.width,
      })
    }

    positionDropdown()
    window.addEventListener('resize', positionDropdown)
    window.addEventListener('scroll', positionDropdown, true)
    return () => {
      window.removeEventListener('resize', positionDropdown)
      window.removeEventListener('scroll', positionDropdown, true)
    }
  }, [isOpen])

  const excluded = new Set(excludedPlayerIds)
  const availablePlayers = results.filter(
    (result) =>
      result.is_active &&
      (!excluded.has(result.id) || result.id === player?.player_id),
  )
  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    const nextQuery = event.target.value
    setQuery(nextQuery)
    setPortalHost(event.currentTarget.closest('dialog') ?? document.body)
    setIsOpen(true)
    if (player !== null && nextQuery !== playerName(player)) onChange(null)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      event.preventDefault()
      setIsOpen(false)
    }
  }

  function selectPlayer(nextPlayer: PlayerResponse) {
    onChange(toSelection(nextPlayer))
    setQuery(`${nextPlayer.first_name} ${nextPlayer.last_name}`)
    setIsOpen(false)
  }

  function handleFocus(event: FocusEvent<HTMLInputElement>) {
    setPortalHost(event.currentTarget.closest('dialog') ?? document.body)
    setIsOpen(true)
  }

  const menu = isOpen && portalHost !== null
    ? createPortal(
        <div
          className="fixed z-dropdown mt-1 max-h-64 overflow-y-auto rounded-lg border border-slate-300 bg-white"
          style={position}
        >
          {isLoading ? (
            <p role="status" className="p-3 text-sm text-slate-700">
              Searching players…
            </p>
          ) : null}
          {errorMessage !== null ? (
            <div role="alert" className="p-3 text-sm text-red-950">
              <p>{errorMessage}</p>
              <button
                type="button"
                className="mt-2 min-h-11 rounded-lg border border-red-800 px-3 font-semibold hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-800 focus:ring-offset-2"
                onMouseDown={(event) => event.preventDefault()}
                onClick={retry}
              >
                Retry player search
              </button>
            </div>
          ) : null}
          {!isLoading &&
          errorMessage === null &&
          availablePlayers.length === 0 ? (
            <p className="p-3 text-sm text-slate-700">No players found</p>
          ) : null}
          {availablePlayers.length > 0 ? (
            <ul id={listboxId} role="listbox" aria-label={label}>
              {availablePlayers.map((result) => (
                <li
                  key={result.id}
                  role="option"
                  aria-selected={result.id === player?.player_id}
                  className="flex min-h-11 cursor-pointer items-center px-3 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectPlayer(result)}
                >
                  {result.first_name} {result.last_name}
                </li>
              ))}
            </ul>
          ) : null}
        </div>,
        portalHost,
      )
    : null

  return (
    <>
      <input
        ref={inputRef}
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-expanded={isOpen}
        aria-label={label}
        autoComplete="off"
        disabled={disabled}
        className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-600 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100"
        placeholder="Search active players"
        value={query}
        onBlur={() => window.setTimeout(() => setIsOpen(false), 0)}
        onChange={handleInput}
        onFocus={handleFocus}
        onKeyDown={handleKeyDown}
      />
      {menu}
    </>
  )
}
