import type { PlayerResponse } from '../../types/player'
import { PLAYER_TYPE_LABELS, formatEnum } from '../../utils/playerLabels'

interface PlayerTypeBadgeProps {
  playerType: PlayerResponse['player_type']
}

export default function PlayerTypeBadge({
  playerType,
}: PlayerTypeBadgeProps) {
  return (
    <span className="inline-flex min-h-6 shrink-0 items-center rounded-md border border-academy bg-academy/10 px-2 py-0.5 text-xs font-semibold leading-5 text-slate-800">
      {formatEnum(playerType, PLAYER_TYPE_LABELS)}
    </span>
  )
}
