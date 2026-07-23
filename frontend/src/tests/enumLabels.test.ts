import { describe, expect, it } from 'vitest'
import {
  BATTING_STYLE_LABELS,
  BOWLING_STYLE_LABELS,
  PLAYER_TYPE_LABELS,
  formatEnum,
} from '../utils/enumLabels'

describe('enum labels', () => {
  it('maps every supported player enum to a readable label', () => {
    expect(BATTING_STYLE_LABELS.right).toBe('Right-Handed')
    expect(BOWLING_STYLE_LABELS['right-arm leg-break']).toBe(
      'Right-Arm Leg-Break',
    )
    expect(PLAYER_TYPE_LABELS['wicket-keeper']).toBe('Wicket-Keeper')
  })

  it('falls back safely for unknown enum values', () => {
    expect(formatEnum('new_style-value', BOWLING_STYLE_LABELS)).toBe(
      'New Style Value',
    )
  })
})
