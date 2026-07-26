import type { ReactNode } from 'react'
import type { PlayerResponse } from '../../types/player'
import PlayerInitialsAvatar from './PlayerInitialsAvatar'

interface PlayerIdentityProps {
  player: PlayerResponse
  avatarSize?: 'card' | 'modal'
  showAllTeams?: boolean
  titleAs?: 'h2' | 'span'
  titleId?: string
  trailing?: ReactNode
}

function getTeamDisplay(
  teams: PlayerResponse['teams'],
  showAllTeams = false,
) {
  if (teams.length === 0) return 'Unassigned'
  if (showAllTeams) return teams.map((team) => team.name).join(', ')
  if (teams.length === 1) return teams[0].name
  return `${teams[0].name} +${teams.length - 1} more`
}

export default function PlayerIdentity({
  player,
  avatarSize = 'card',
  showAllTeams = false,
  titleAs: TitleElement = 'span',
  titleId,
  trailing,
}: PlayerIdentityProps) {
  const fullName = `${player.first_name} ${player.last_name}`.trim()

  return (
    <span className="flex min-w-0 items-start gap-3">
      <PlayerInitialsAvatar
        firstName={player.first_name}
        lastName={player.last_name}
        size={avatarSize}
      />
      <span className="min-w-0 flex-1">
        <TitleElement
          id={titleId}
          className={`block break-words font-bold text-slate-900 ${
            avatarSize === 'modal'
              ? 'text-2xl leading-8 tracking-tight'
              : 'text-base leading-5'
          }`}
        >
          {fullName}
        </TitleElement>
        <span className="mt-1 block break-words text-sm leading-5 text-slate-600">
          {getTeamDisplay(player.teams, showAllTeams)}
        </span>
      </span>
      {trailing}
    </span>
  )
}
