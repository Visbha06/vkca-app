import type { TeamRosterSelection } from '../../types/team'
import TeamRosterRow from './TeamRosterRow'

interface TeamRosterFieldsProps {
  players: (TeamRosterSelection | null)[]
  error?: string
  disabled: boolean
  onChange: (index: number, player: TeamRosterSelection | null) => void
  onPlayerInfo: (player: TeamRosterSelection) => void
}

export default function TeamRosterFields({
  players,
  error,
  disabled,
  onChange,
  onPlayerInfo,
}: TeamRosterFieldsProps) {
  const selectedPlayerIds = players.flatMap((player) =>
    player === null ? [] : [player.player_id],
  )

  return (
    <section aria-labelledby="team-roster-title">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 id="team-roster-title" className="text-base font-bold text-slate-900">
            Roster
          </h3>
          <p className="mt-1 text-sm text-slate-700">
            Select 7–15 active players in roster order.
          </p>
        </div>
        <p className="text-sm font-semibold text-slate-700">
          {selectedPlayerIds.length} / 15 selected
        </p>
      </div>
      {error ? (
        <p id="team-roster-error" className="mt-3 text-sm font-medium text-red-800">
          {error}
        </p>
      ) : null}
      <ol
        aria-describedby={error ? 'team-roster-error' : undefined}
        className="mt-3 border-y border-slate-200"
      >
        {players.map((player, index) => (
          <TeamRosterRow
            key={index}
            index={index}
            player={player}
            selectedPlayerIds={selectedPlayerIds}
            disabled={disabled}
            onChange={(nextPlayer) => onChange(index, nextPlayer)}
            onPlayerInfo={onPlayerInfo}
          />
        ))}
      </ol>
    </section>
  )
}
