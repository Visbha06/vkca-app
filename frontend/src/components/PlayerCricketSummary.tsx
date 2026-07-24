import type { PlayerResponse } from '../types/player'
import {
  BATTING_STYLE_LABELS,
  BOWLING_STYLE_LABELS,
  formatEnum,
} from '../utils/enumLabels'

interface PlayerCricketSummaryProps {
  compact?: boolean
  player: PlayerResponse
}

export default function PlayerCricketSummary({
  compact = false,
  player,
}: PlayerCricketSummaryProps) {
  const battingStyle = formatEnum(player.batting_style, BATTING_STYLE_LABELS)
  const bowlingStyle = formatEnum(player.bowling_style, BOWLING_STYLE_LABELS)

  if (player.player_type === 'bowler') {
    return <span>Bowling: {bowlingStyle}</span>
  }

  if (
    player.player_type === 'batter' ||
    player.player_type === 'wicket-keeper'
  ) {
    return <span>Batting: {battingStyle}</span>
  }

  return (
    <span>
      {compact
        ? `Bat: ${battingStyle} · Bowl: ${bowlingStyle}`
        : `Batting: ${battingStyle} · Bowling: ${bowlingStyle}`}
    </span>
  )
}
