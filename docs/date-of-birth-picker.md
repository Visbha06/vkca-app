# Date of Birth Picker

## Purpose

The reusable date-of-birth picker replaces the browser-native date input in
the shared player create and edit form. It gives coaches a consistent,
timezone-safe way to select a known birth date without stepping through years
one month at a time.

## User interaction

The Date of birth label identifies one button-style trigger. An empty form
shows `Select date of birth`; an existing ISO value is displayed in long form,
such as `August 17, 2005`. Activating the trigger opens a non-modal calendar
next to it. Coaches can:

- select a month and year directly with native select controls;
- move one month at a time with the labelled previous and next buttons;
- review a Sunday-first, seven-column day grid with only the complete week rows
  required by the displayed month; and
- choose an available day to update the form and close the calendar.

Create and edit forms continue to store and submit `dateOfBirth` as
`YYYY-MM-DD`. Opening the edit picker uses the player's saved month, year, and
day. Opening an empty picker uses the current month but does not select or
submit a date.

## Component and date logic

The public control is
`frontend/src/shared/components/forms/date-of-birth/DateOfBirthPicker.tsx`.
Its neighboring header, grid, state, and anchored-positioning modules keep
rendering, keyboard behavior, calendar state, and viewport positioning
separate. Shared calendar parsing and arithmetic live in
`frontend/src/shared/utils/calendarDate.ts`; existing display formatting in
`frontend/src/shared/utils/formatDate.ts` now uses that parser.

ISO strings are parsed into explicit `{ year, month, day }` parts. Calendar
arithmetic uses UTC only as an internal calculation mechanism created from
those parts; the form never stores a `Date`, timestamp, or locale-formatted
value. Human-readable formatting specifies UTC explicitly, preventing a
selected calendar day from shifting with the user's time zone.

## Date restrictions

The selectable range is calculated when the picker mounts:

- earliest: exactly 100 calendar years before the user's local current date;
- latest: the user's local current date.

Future dates and dates before the earliest limit are disabled. Boundary month
navigation and out-of-range month options are also disabled. Month and year
changes clamp the focused day to the target month's valid day count, including
February and leap years. Calendar generation returns 28, 35, or 42
chronologically ordered cells, so four-, five-, and six-week months do not
receive an empty trailing week. Outside-month and disabled dates use
transparent backgrounds with distinct muted text treatments instead of filled
tiles. Leading and trailing outside-month dates share the same styling.

## Accessibility and responsive behavior

The trigger retains the visible form label, exposes its displayed value as an
accessible description, preserves `aria-invalid` and the field error
relationship, and has one 44px-minimum tab stop. The calendar uses a
non-modal dialog landmark, labelled icon controls, native selects, an ARIA
grid, weekday headers, `aria-selected`, `aria-current="date"`, and native
disabled semantics.

Opening focuses the selected day or today's date. Arrow keys move by one day
or one week and cross month boundaries. Enter or Space selects the focused
date. Escape and outside pointer interaction close the calendar and restore
focus to the trigger. Month and year changes retain focus on their select.

The calendar is rendered through a local portal with fixed positioning so it
is not clipped by the legacy player modal and remains compatible with the
shared native dialog. It flips above the trigger when needed, clamps to the
viewport, uses the semantic `z-dropdown` layer, and scrolls internally when
vertical space is constrained. At 320px it uses the viewport width while
retaining 44px day targets and avoiding horizontal page overflow.

## Dependencies and testing

No dependency was added or removed. The implementation reuses React portals,
the existing calendar icon, Tailwind design tokens, the academy focus
treatment, and the semantic overlay scale.

Unit and component coverage includes empty and existing values, ISO display,
opening and dismissal, focus restoration, errors, disabled state, direct
month/year changes, bounded navigation, future dates, pointer and keyboard
selection, arrow-key month crossings, leap years, invalid dates, and
timezone-safe formatting. Player form, Add Player, and Edit Player tests cover
the preserved form and submission contracts.

`frontend/e2e/players-flow.spec.ts` selects and saves a birth date through the
custom calendar, verifies the stored ISO value and displayed player detail,
and checks calendar bounds, 44px day targets, focus restoration, and
horizontal overflow at 320px, 390px, 768px, 1280px, and 1920px widths.
