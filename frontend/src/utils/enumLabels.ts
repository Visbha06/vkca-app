import type {
  BattingStyle,
  BowlingStyle,
  PlayerType,
} from '../types/player'

export const BATTING_STYLE_LABELS: Readonly<Record<BattingStyle, string>> = {
  right: 'Right-Handed',
  left: 'Left-Handed',
}

export const BOWLING_STYLE_LABELS: Readonly<Record<BowlingStyle, string>> = {
  'right-arm fast': 'Right-Arm Fast',
  'right-arm medium': 'Right-Arm Medium',
  'right-arm off-break': 'Right-Arm Off-Break',
  'right-arm leg-break': 'Right-Arm Leg-Break',
  'left-arm fast': 'Left-Arm Fast',
  'left-arm medium': 'Left-Arm Medium',
  'left-arm orthodox': 'Left-Arm Orthodox',
  'left-arm unorthodox': 'Left-Arm Unorthodox',
}

export const PLAYER_TYPE_LABELS: Readonly<Record<PlayerType, string>> = {
  batter: 'Batter',
  bowler: 'Bowler',
  'all-rounder': 'All-Rounder',
  'wicket-keeper': 'Wicket-Keeper',
}

export function formatEnum(
  raw: string,
  labels: Readonly<Record<string, string>>,
) {
  const mappedLabel = labels[raw]
  if (mappedLabel !== undefined) return mappedLabel

  return raw
    .trim()
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\p{L}/gu, (letter) => letter.toLocaleUpperCase())
}
