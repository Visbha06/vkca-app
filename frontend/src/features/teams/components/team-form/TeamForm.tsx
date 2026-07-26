import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import type {
  AgeGroup,
  TeamCreatePayload,
  TeamResponse,
  TeamRosterResponse,
  TeamRosterSelection,
  TeamUpdatePayload,
} from '../../types/team'
import TeamDetailsFields from './TeamDetailsFields'
import TeamRosterList from './TeamRosterList'
interface TeamFormProps {
  team?: TeamResponse
  roster?: TeamRosterResponse
  initialRoster?: TeamRosterSelection[]
  isSubmitting?: boolean
  errorMessage?: string | null
  errorAction?: ReactNode
  onCancel: () => void
  onChange?: () => void
  onDirtyChange?: (isDirty: boolean) => void
  onPlayerInfo?: (player: TeamRosterSelection) => void
  onSubmit: (
    payload: TeamCreatePayload | TeamUpdatePayload,
  ) => Promise<void> | void
}
interface FormErrors {
  name?: string
  ageGroup?: string
  roster?: string
}
function rosterSlots(
  roster?: TeamRosterResponse,
  initialRoster?: TeamRosterSelection[],
) {
  const players = roster?.players ?? initialRoster ?? []
  const selections: (TeamRosterSelection | null)[] = players.map((player) => ({
    player_id: player.player_id,
    first_name: player.first_name,
    last_name: player.last_name,
    is_active: player.is_active,
  }))
  return [...selections, ...Array<null>(15).fill(null)].slice(0, 15)
}
function snapshot(
  name: string,
  ageGroup: AgeGroup | '',
  players: (TeamRosterSelection | null)[],
) {
  return JSON.stringify({
    name,
    ageGroup,
    playerIds: players.map((player) => player?.player_id ?? null),
  })
}

export default function TeamForm({
  team,
  roster,
  initialRoster,
  isSubmitting = false,
  errorMessage = null,
  errorAction,
  onCancel,
  onChange,
  onDirtyChange,
  onPlayerInfo = () => undefined,
  onSubmit,
}: TeamFormProps) {
  const initialPlayers = useMemo(
    () => rosterSlots(roster, initialRoster),
    [initialRoster, roster],
  )
  const initialName = team?.name ?? ''
  const initialAgeGroup = team?.age_group ?? ''
  const initialSnapshot = useMemo(
    () => snapshot(initialName, initialAgeGroup, initialPlayers),
    [initialAgeGroup, initialName, initialPlayers],
  )
  const [name, setName] = useState(initialName)
  const [ageGroup, setAgeGroup] = useState<AgeGroup | ''>(initialAgeGroup)
  const [players, setPlayers] = useState(initialPlayers)
  const [errors, setErrors] = useState<FormErrors>({})
  const isEditing = team !== undefined
  const isDirty =
    snapshot(name, ageGroup, players) !== initialSnapshot

  useEffect(() => {
    onDirtyChange?.(isDirty)
  }, [isDirty, onDirtyChange])

  function updatePlayers(nextPlayers: (TeamRosterSelection | null)[]) {
    setPlayers(nextPlayers)
    setErrors((current) => ({ ...current, roster: undefined }))
    onChange?.()
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return
    const selectedPlayers = players.filter(
      (player): player is TeamRosterSelection => player !== null,
    )
    const playerIds = selectedPlayers.map((player) => player.player_id)
    const hasDuplicates = new Set(playerIds).size !== playerIds.length
    const hasInactivePlayers = selectedPlayers.some((player) => !player.is_active)
    const nextErrors: FormErrors = {
      ...(!name.trim() ? { name: 'Enter a team name.' } : {}),
      ...(ageGroup === '' ? { ageGroup: 'Choose an age group.' } : {}),
      ...(selectedPlayers.length < 7
        ? { roster: 'Select at least 7 players.' }
        : selectedPlayers.length > 15
          ? { roster: 'Select no more than 15 players.' }
          : hasInactivePlayers
            ? { roster: 'Replace inactive players before saving.' }
            : hasDuplicates
              ? { roster: 'Each player can only be selected once.' }
              : {}),
    }
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0 || ageGroup === '') return

    const createPayload: TeamCreatePayload = {
      name: name.trim(),
      age_group: ageGroup,
      player_ids: playerIds,
    }
    void onSubmit(
      team === undefined
        ? createPayload
        : {
            ...createPayload,
            version_number: team.version_number,
          },
    )
  }

  return (
    <form noValidate onSubmit={handleSubmit}>
      <div className="space-y-6 p-5 sm:p-6">
        {errorMessage !== null ? (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950"
          >
            <p className="font-semibold">{errorMessage}</p>
            {errorAction}
          </div>
        ) : null}
        {isSubmitting ? (
          <span role="status" className="sr-only">
            {isEditing ? 'Updating team' : 'Creating team'}
          </span>
        ) : null}

        <TeamDetailsFields
          name={name}
          ageGroup={ageGroup}
          nameError={errors.name}
          ageGroupError={errors.ageGroup}
          disabled={isSubmitting}
          onNameChange={(nextName) => {
            setName(nextName)
            setErrors((current) => ({ ...current, name: undefined }))
            onChange?.()
          }}
          onAgeGroupChange={(nextAgeGroup) => {
            setAgeGroup(nextAgeGroup)
            setErrors((current) => ({ ...current, ageGroup: undefined }))
            onChange?.()
          }}
        />
        <section aria-labelledby="team-roster-title">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <h3 id="team-roster-title" className="text-base font-bold text-slate-900">
                Roster
              </h3>
              <p className="mt-1 text-sm text-slate-700">
                Select 7–15 active players in roster order. Drag a grip or use Move Up and Move Down.
              </p>
            </div>
            <p className="text-sm font-semibold text-slate-700">
              {players.filter((player) => player !== null).length} / 15 selected
            </p>
          </div>
          {errors.roster ? (
            <p id="team-roster-error" className="mt-3 text-sm font-medium text-red-800">
              {errors.roster}
            </p>
          ) : null}
          <div aria-describedby={errors.roster ? 'team-roster-error' : undefined}>
            <TeamRosterList
              players={players}
              disabled={isSubmitting}
              onPlayersChange={updatePlayers}
              onPlayerInfo={onPlayerInfo}
            />
          </div>
        </section>
        {isEditing ? <input type="hidden" name="version_number" value={team.version_number} /> : null}
      </div>

      <div className="flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end sm:p-6">
        <button type="button" disabled={isSubmitting} className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-slate-400" onClick={onCancel}>Cancel</button>
        <button type="submit" disabled={isSubmitting} className="min-h-11 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-academy focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-400">
          {isSubmitting ? (isEditing ? 'Saving changes…' : 'Creating team…') : (isEditing ? 'Save changes' : 'Create team')}
        </button>
      </div>
    </form>
  )
}
