interface CoachIdentityFieldsProps {
  firstName: string
  lastName: string
  email: string
  firstNameError?: string
  lastNameError?: string
  emailError?: string | null
  isDisabled: boolean
  onFirstNameChange: (value: string) => void
  onLastNameChange: (value: string) => void
  onEmailChange: (value: string) => void
}

const inputClass =
  'mt-2 min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-base text-slate-900 placeholder:text-slate-500 focus:border-academy focus:outline-none focus:ring-2 focus:ring-academy/40 disabled:cursor-not-allowed disabled:bg-slate-100'

export default function CoachIdentityFields({
  firstName,
  lastName,
  email,
  firstNameError,
  lastNameError,
  emailError,
  isDisabled,
  onFirstNameChange,
  onLastNameChange,
  onEmailChange,
}: CoachIdentityFieldsProps) {
  return (
    <>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-800">
          First name
          <input
            name="first_name"
            autoComplete="given-name"
            disabled={isDisabled}
            aria-invalid={firstNameError ? true : undefined}
            aria-describedby={firstNameError ? 'first-name-error' : undefined}
            className={inputClass}
            value={firstName}
            onChange={(event) => onFirstNameChange(event.target.value)}
          />
          {firstNameError ? (
            <span
              id="first-name-error"
              className="mt-2 block font-medium text-red-800"
            >
              {firstNameError}
            </span>
          ) : null}
        </label>

        <label className="text-sm font-semibold text-slate-800">
          Last name
          <input
            name="last_name"
            autoComplete="family-name"
            disabled={isDisabled}
            aria-invalid={lastNameError ? true : undefined}
            aria-describedby={lastNameError ? 'last-name-error' : undefined}
            className={inputClass}
            value={lastName}
            onChange={(event) => onLastNameChange(event.target.value)}
          />
          {lastNameError ? (
            <span
              id="last-name-error"
              className="mt-2 block font-medium text-red-800"
            >
              {lastNameError}
            </span>
          ) : null}
        </label>
      </div>

      <label className="block text-sm font-semibold text-slate-800">
        Email address
        <input
          name="email"
          type="email"
          autoComplete="email"
          disabled={isDisabled}
          aria-invalid={emailError ? true : undefined}
          aria-describedby={emailError ? 'coach-email-error' : undefined}
          className={inputClass}
          value={email}
          onChange={(event) => onEmailChange(event.target.value)}
        />
        {emailError ? (
          <span
            id="coach-email-error"
            className="mt-2 block font-medium text-red-800"
          >
            {emailError}
          </span>
        ) : null}
      </label>
    </>
  )
}
