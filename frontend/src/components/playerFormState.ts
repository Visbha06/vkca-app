import type {
  PlayerCreatePayload,
  PlayerResponse,
} from '../types/player'
import type { PlayerFormValues } from './PlayerFormFields'
import type { MetadataRow } from './PlayerMetadataFields'

const emptyValues: PlayerFormValues = {
  firstName: '',
  lastName: '',
  dateOfBirth: '',
  bio: '',
  battingStyle: '',
  bowlingStyle: '',
  playerType: '',
}

function metadataValueToText(value: unknown) {
  if (typeof value === 'string') return value
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function playerFormValues(player?: PlayerResponse): PlayerFormValues {
  if (player === undefined) return emptyValues

  return {
    firstName: player.first_name,
    lastName: player.last_name,
    dateOfBirth: player.date_of_birth,
    bio: player.bio ?? '',
    battingStyle: player.batting_style,
    bowlingStyle: player.bowling_style,
    playerType: player.player_type,
  }
}

export function playerMetadataRows(player?: PlayerResponse): MetadataRow[] {
  const entries = Object.entries(player?.player_metadata ?? {})
  if (entries.length === 0) {
    return [{ id: 'metadata-1', key: '', value: '' }]
  }

  return entries.map(([key, value], index) => ({
    id: `metadata-${index + 1}`,
    key,
    value: metadataValueToText(value),
  }))
}

function normalizedMetadata(
  rows: MetadataRow[],
  originalMetadata: Record<string, unknown> = {},
) {
  return Object.fromEntries(
    rows
      .filter((row) => row.key.trim())
      .map((row) => {
        const key = row.key.trim()
        const value = row.value.trim()
        const originalValue = originalMetadata[key]
        const canPreserveOriginal =
          Object.hasOwn(originalMetadata, key) &&
          metadataValueToText(originalValue) === value
        return [key, canPreserveOriginal ? originalValue : value]
      }),
  )
}

export function playerFormIsDirty(
  values: PlayerFormValues,
  rows: MetadataRow[],
  initialValues: PlayerFormValues,
  initialRows: MetadataRow[],
) {
  return (
    JSON.stringify(values) !== JSON.stringify(initialValues) ||
    JSON.stringify(normalizedMetadata(rows)) !==
      JSON.stringify(normalizedMetadata(initialRows))
  )
}

export function playerFormPayload(
  values: PlayerFormValues,
  rows: MetadataRow[],
  player?: PlayerResponse,
): PlayerCreatePayload {
  return {
    first_name: values.firstName.trim(),
    last_name: values.lastName.trim(),
    date_of_birth: values.dateOfBirth,
    bio: values.bio.trim() || null,
    batting_style: values.battingStyle as PlayerCreatePayload['batting_style'],
    bowling_style: values.bowlingStyle as PlayerCreatePayload['bowling_style'],
    player_type: values.playerType as PlayerCreatePayload['player_type'],
    player_metadata: normalizedMetadata(rows, player?.player_metadata),
  }
}
