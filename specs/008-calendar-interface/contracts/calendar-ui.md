# Calendar UI Contract

## Page structure

- The route remains `/calendar` inside the authenticated application shell.
- The page has one `h1` Calendar heading, a calendar section, and a Today section beneath it.
- The calendar header places the active year selector on the left and Create Event for coaches on the right; previous/next month controls sit at the calendar’s upper-right area.
- The monthly view remains a seven-column grid at every viewport. It may compact labels on mobile but never becomes a third-party week/day view or introduces page-wide horizontal overflow.

## Roles

| Role | Read calendar | View details | Create | Edit | Delete |
|---|---:|---:|---:|---:|---:|
| Head Coach | Yes | Yes | Yes | Yes | Yes |
| Assistant Coach | Yes | Yes | Yes | Yes | Yes |
| Player | Yes | Yes | No | No | No |

The UI hides mutation controls for Players, while the backend independently returns `403` for attempted mutations.

## Calendar interaction

- Weekday headers use semantic labels.
- Each date cell exposes its full academy date, whether it is current/selected/adjacent-month, and a concise event summary to assistive technology.
- Arrow keys move focus by day; month navigation and year selection restore focus to the logical date/month control.
- Current date uses academy-teal emphasis plus a non-color treatment such as a border or label. Adjacent dates use muted copy and remain distinguishable by date context, not color alone.
- Event type icons have text alternatives. Event entries are buttons with full accessible names even if their visible mobile label is shortened.
- Only three entries are rendered in a cell. `+N more` is a keyboard-accessible button that opens the full-day view.

## Loading, empty, and errors

- Initial calendar and Today loading show structure-preserving skeleton/status content.
- Navigation retains the grid shape and communicates loading without leaving stale events labeled as the new month.
- Calendar and Today failures show concise safe copy and Retry.
- Details can open with a loading state and exposes Retry if the instance request fails.
- Form requests disable repeat submission and announce progress. Failed requests preserve values.
- `409` displays a conflict message and Reload; it never automatically retries the mutation.
- Series-update exception removal displays the affected dates and requires explicit Continue or Cancel before saving.
- Empty Today uses exactly `No events scheduled for today.`; an empty daily overflow view has a contextual no-events message.

## Modal and form behavior

- Details, create/edit forms, daily overflow, removal warning, and deletion confirmations use the existing modal/focus-trapping patterns.
- Modals have accessible labels/descriptions, Escape closing when no unsafe operation is running, a visible close control, locked background scrolling, internal small-viewport scrolling, and focus restoration.
- Create/Edit forms use associated error text, an unsaved-change confirmation with Continue editing and Discard changes, and preserve dirty values when requests fail.
- Recurrence controls expose exactly one frequency and exactly one termination mode. All-day is only offered for Miscellaneous.

## Visual and responsive constraints

- Follow `PRODUCT.md` and `DESIGN.md`: cool canvas, white surfaces, slate ink/body copy, restrained academy teal, fine boundary lines, system typography, and disciplined operational density.
- Interactive controls use at least 44px touch targets and visible academy-teal focus rings with forced-colors support.
- Layout uses existing Tailwind spacing/breakpoint conventions; no arbitrary pixel utility values.
- At 320px, header controls wrap or stack, fields stack, event labels truncate safely with full accessible labels, Today remains readable, and modal content scrolls within the viewport.
