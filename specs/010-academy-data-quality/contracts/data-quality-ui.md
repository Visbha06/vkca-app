# Data Quality UI Contract

## Route and navigation

- Route: `/data-quality` inside the protected application layout.
- Route wrapper: existing `HeadCoachRoute`.
- Sidebar order: `Audit Log`, then `Data Quality`, both Head Coach-only.
- Assistant Coaches and Players do not see the item. Direct navigation renders
  the existing Forbidden experience and does not request the Data Quality API.
- Navigate-to-Fix uses existing base workflows: `/players`, `/teams`,
  `/coaches`, or `/calendar`. It does not introduce a new entity deep-link
  selection contract.

## Page structure

The page follows the existing Audit Log layout and `DESIGN.md` visual language:

1. Page heading and short operational explanation.
2. One shared summary band for total, Critical, Warning, and Info counts, with
   optional grouped domain counts.
3. Filter controls for severity, domain, and rule, plus Clear filters.
4. A polite live status describing loading, refresh, or result count.
5. Finding list/cards with text severity, title, affected entity, explanation,
   recommended action, and an action control.
6. Existing bounded Pagination when more than one page exists.

Use cool canvas and white surfaces, slate text/borders, restrained Academy
Teal for focus and wayfinding, flat containers, and standard Tailwind spacing.
Controls are at least 44px-class touch targets. Severity is never conveyed by
color alone.

## Finding actions

### Navigate to Fix

Show for subjective or review-only findings, including normalized player
duplicates, team naming conflicts, missing coach assignments, active Assistant
Coaches without teams, invalid coach roles, calendar issues, and sole Head
Coach integrity. Navigation preserves the finding label in the current-page
status/toast long enough to identify the target.

### Direct remediation

Show only when the API supplies a supported typed action:

- Normalize roster order.
- Remove one inactive player membership.
- Remove one inactive Assistant Coach/team assignment.

Never show a direct action for a Head Coach assignment or the sole Head Coach
integrity rule. Removal actions open the existing `ModalDialog` pattern. The
dialog names the exact team/player/Assistant Coach relationship, explains that
the change is one relationship only, and has Cancel and explicit Confirm
controls. Confirmation is disabled while submitting.

## State contract

| State | Required behavior |
| --- | --- |
| Initial loading | Structure-preserving skeleton and one polite loading announcement. |
| Background refresh | Keep prior findings visible, set results `aria-busy`, show updating status, and avoid an empty-state flash. |
| Initial error | Non-sensitive error state with keyboard-operable Retry. |
| Background error | Keep prior findings visible, show retryable alert, and do not discard the last successful result. |
| Healthy | Positive empty state with the exact user-facing message “No data quality issues found” and supporting text. |
| Filtered no-results | “No findings match these filters” and Clear filters. Global summary remains visible. |
| Unauthorized | Existing `ForbiddenPage`; no findings request for role-protected frontend navigation. |
| Remediation success | Accessible success status/toast, immediate re-evaluation, and disappearance of resolved findings. |
| Remediation conflict/failure | Safe explanation, no success implication, current findings retained where possible, and Refresh/retry path. |

## State and request behavior

The page hook follows `useBusinessAudit` conventions:

- default page size is 20;
- filter changes reset to page 1;
- query requests use `AbortController` and ignore superseded responses;
- refresh/retry preserves successful data while a new request is pending;
- the hook does not run when the authenticated role is not Head Coach;
- direct remediation sets a submitting state, then refreshes the read result;
- a 409 conflict is rendered as stale data requiring refresh/re-evaluation.

The TypeScript types mirror the Pydantic API contracts. No `any` or inline
untyped API object is permitted.

## Accessibility and responsive behavior

- Use semantic headings, landmarks, labels, lists, buttons, and status regions.
- Use visible focus rings and keyboard-operable filters, pagination, cards, and
  dialogs.
- `ModalDialog` supplies focus containment, Escape handling, restoration, and
  portal behavior; the page supplies semantic labels and submission status.
- Severity labels include text such as “Critical”, “Warning”, or “Info”.
- Filters wrap/stack at 320px; finding content and dialogs use min-width-safe
  layout and no page-level horizontal overflow.
- Automated frontend tests cover keyboard interactions and Playwright covers
  320px, 768px, and desktop render behavior where practical.
