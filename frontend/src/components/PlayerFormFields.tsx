import type {
  BattingStyle,
  BowlingStyle,
  PlayerType,
} from '../types/player'
import {
  BATTING_STYLE_LABELS,
  BOWLING_STYLE_LABELS,
  PLAYER_TYPE_LABELS,
} from '../utils/enumLabels'

export interface PlayerFormValues {
  firstName: string
  lastName: string
  dateOfBirth: string
  bio: string
  battingStyle: BattingStyle | ''
  bowlingStyle: BowlingStyle | ''
  playerType: PlayerType | ''
}

export type PlayerFieldErrors = Partial<Record<keyof PlayerFormValues, string>>

interface PlayerFormFieldsProps {
  values: PlayerFormValues
  errors: PlayerFieldErrors
  disabled: boolean
  onChange: <Key extends keyof PlayerFormValues>(
    field: Key,
    value: PlayerFormValues[Key],
  ) => void
}

const inputClass =
  'min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-500 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500'

function FieldError({ id, message }: { id: string; message?: string }) {
  if (message === undefined) return null
  return (
    <p id={id} className="mt-2 text-sm font-medium text-red-800">
      {message}
    </p>
  )
}

export default function PlayerFormFields({
  values,
  errors,
  disabled,
  onChange,
}: PlayerFormFieldsProps) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
      <div>
        <label htmlFor="player-first-name" className="text-sm font-semibold text-slate-800">
          First name
        </label>
        <input
          id="player-first-name"
          data-modal-initial-focus
          value={values.firstName}
          disabled={disabled}
          aria-invalid={errors.firstName !== undefined}
          aria-describedby={errors.firstName ? 'player-first-name-error' : undefined}
          className={`mt-2 ${inputClass}`}
          onChange={(event) => onChange('firstName', event.target.value)}
        />
        <FieldError id="player-first-name-error" message={errors.firstName} />
      </div>

      <div>
        <label htmlFor="player-last-name" className="text-sm font-semibold text-slate-800">
          Last name
        </label>
        <input
          id="player-last-name"
          value={values.lastName}
          disabled={disabled}
          aria-invalid={errors.lastName !== undefined}
          aria-describedby={errors.lastName ? 'player-last-name-error' : undefined}
          className={`mt-2 ${inputClass}`}
          onChange={(event) => onChange('lastName', event.target.value)}
        />
        <FieldError id="player-last-name-error" message={errors.lastName} />
      </div>

      <div>
        <label htmlFor="player-date-of-birth" className="text-sm font-semibold text-slate-800">
          Date of birth
        </label>
        <input
          id="player-date-of-birth"
          type="date"
          value={values.dateOfBirth}
          disabled={disabled}
          aria-invalid={errors.dateOfBirth !== undefined}
          aria-describedby={errors.dateOfBirth ? 'player-date-error' : undefined}
          className={`mt-2 ${inputClass}`}
          onChange={(event) => onChange('dateOfBirth', event.target.value)}
        />
        <FieldError id="player-date-error" message={errors.dateOfBirth} />
      </div>

      <div>
        <label htmlFor="player-type" className="text-sm font-semibold text-slate-800">
          Player type
        </label>
        <select
          id="player-type"
          value={values.playerType}
          disabled={disabled}
          aria-invalid={errors.playerType !== undefined}
          aria-describedby={errors.playerType ? 'player-type-error' : undefined}
          className={`mt-2 ${inputClass}`}
          onChange={(event) => onChange('playerType', event.target.value as PlayerType | '')}
        >
          <option value="">Select player type</option>
          {Object.entries(PLAYER_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <FieldError id="player-type-error" message={errors.playerType} />
      </div>

      <div>
        <label htmlFor="player-batting-style" className="text-sm font-semibold text-slate-800">
          Batting style
        </label>
        <select
          id="player-batting-style"
          value={values.battingStyle}
          disabled={disabled}
          aria-invalid={errors.battingStyle !== undefined}
          aria-describedby={errors.battingStyle ? 'player-batting-error' : undefined}
          className={`mt-2 ${inputClass}`}
          onChange={(event) => onChange('battingStyle', event.target.value as BattingStyle | '')}
        >
          <option value="">Select batting style</option>
          {Object.entries(BATTING_STYLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <FieldError id="player-batting-error" message={errors.battingStyle} />
      </div>

      <div>
        <label htmlFor="player-bowling-style" className="text-sm font-semibold text-slate-800">
          Bowling style
        </label>
        <select
          id="player-bowling-style"
          value={values.bowlingStyle}
          disabled={disabled}
          aria-invalid={errors.bowlingStyle !== undefined}
          aria-describedby={errors.bowlingStyle ? 'player-bowling-error' : undefined}
          className={`mt-2 ${inputClass}`}
          onChange={(event) => onChange('bowlingStyle', event.target.value as BowlingStyle | '')}
        >
          <option value="">Select bowling style</option>
          {Object.entries(BOWLING_STYLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <FieldError id="player-bowling-error" message={errors.bowlingStyle} />
      </div>

      <div className="sm:col-span-2">
        <label htmlFor="player-bio" className="text-sm font-semibold text-slate-800">
          Bio <span className="font-normal text-slate-600">(optional)</span>
        </label>
        <textarea
          id="player-bio"
          rows={4}
          value={values.bio}
          disabled={disabled}
          className={`mt-2 py-3 ${inputClass}`}
          placeholder="Add coaching notes or a short player biography"
          onChange={(event) => onChange('bio', event.target.value)}
        />
      </div>
    </div>
  )
}
