# Business Audit UI Contract

**Feature**: 009-business-audit-log

## Navigation and route

- Add `Audit Log` immediately beneath `Calendar` in the sidebar.
- Render the item only when `user.role === "head coach"`.
- Add `/audit-log` under the authenticated application layout.
- A Head Coach sees the Audit Log page.
- Assistant Coaches and Players see no navigation item and receive the existing generic forbidden experience for direct navigation; the backend remains authoritative.
- The existing authentication audit page and security-log terminology are not reused.

## Audit Log page

Page structure:

1. Existing application shell and page-header pattern.
2. Filter region with labeled actor options loaded from the bounded Head Coach-only actor-options query, action category, action type, entity type, start date, end date, and clear/apply controls as appropriate.
3. Accessible result-count/status announcement.
4. Newest-first audit-event list.
5. Existing pagination component when more than one page exists.

Each event item presents:

- actor display-name snapshot;
- actor role snapshot;
- visible action category text and a category-appropriate icon;
- safe human-readable summary;
- target label snapshot;
- academy-local absolute timestamp;
- native keyboard-operable disclosure when safe details are useful.

Disclosure details may include action type, role snapshot, entity type, target label, safe changed-field summary, related IDs, and request ID. They never show raw payloads, credentials, tokens, secrets, stack traces, raw exception text, or unrestricted personal information.

## Page states

- **Loading**: visible or assistive-technology-readable loading status; pagination and duplicate requests disabled.
- **Initial empty**: clear message that no business audit history exists.
- **Filtered no-results**: distinct message that no events match the selected filters, with a clear-filters action.
- **Error**: safe alert with Retry; no raw backend exception text.
- **Unauthorized**: existing forbidden page/route behavior, with no event data rendered.
- **Results changed**: polite live announcement with result count or no-results status; filter changes reset to page 1.

## Dashboard recent activity

- The section keeps its current `Recent academy activity` placement and timeline composition.
- It renders only for Head Coaches.
- It requests at most four events from the bounded recent route.
- It displays category icon plus visible title/summary, supporting description when useful, and relative academy-local time.
- It provides `View all activity` linking to `/audit-log`.
- It shows a compact empty message when there are no events.
- It shows a compact inline error and Retry when the recent request fails; summary and upcoming-events sections remain usable.

## Responsive and accessibility contract

- The page works from 320px through desktop widths with wrapping/stacking filters and pagination.
- There is no page-level horizontal overflow.
- All controls have visible labels or accessible names, visible focus, keyboard operation, and touch-friendly targets.
- Event disclosures are keyboard operable and preserve focus behavior.
- Loading, errors, filter changes, expansion state, and result counts use existing `role="status"`, `role="alert"`, `aria-live`, and `aria-busy` patterns where appropriate.
- Category meaning is never communicated by icon or color alone.
- Timestamps are formatted with `America/Los_Angeles`; stored ISO timestamps remain the source of truth.
