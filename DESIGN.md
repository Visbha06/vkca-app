---
name: VK Cricket Academy Portal
description: An open, disciplined operations interface for academy coaches and players.
colors:
  academy-teal: "#559eac"
  academy-teal-wash: "#eef5f7"
  academy-teal-soft: "#ddecee"
  practice-night: "#0f172a"
  slate-ink: "#1e293b"
  body-copy: "#475569"
  muted-copy: "#64748b"
  cool-canvas: "#f8fafc"
  clubhouse-white: "#ffffff"
  boundary-line: "#e2e8f0"
  danger-action: "#991b1b"
  error-surface: "#fef2f2"
  warning-surface: "#fffbeb"
  success-marker: "#34d399"
typography:
  headline:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "2.25rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  title:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.practice-night}"
    textColor: "{colors.clubhouse-white}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "44px"
  quick-action:
    backgroundColor: "{colors.clubhouse-white}"
    textColor: "{colors.practice-night}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "44px"
  sidebar-nav-item:
    backgroundColor: "{colors.practice-night}"
    textColor: "{colors.clubhouse-white}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "44px"
  sidebar-nav-item-active:
    backgroundColor: "{colors.clubhouse-white}"
    textColor: "{colors.practice-night}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "44px"
  dashboard-surface:
    backgroundColor: "{colors.clubhouse-white}"
    textColor: "{colors.practice-night}"
    rounded: "{rounded.lg}"
    padding: "24px"
  profile-card:
    backgroundColor: "{colors.clubhouse-white}"
    textColor: "{colors.practice-night}"
    rounded: "{rounded.lg}"
    padding: "12px"
  initials-avatar-card:
    backgroundColor: "{colors.academy-teal-soft}"
    textColor: "{colors.practice-night}"
    rounded: "{rounded.full}"
    size: "44px"
  player-type-badge:
    backgroundColor: "{colors.academy-teal-wash}"
    textColor: "{colors.slate-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
    height: "24px"
  modal-surface:
    backgroundColor: "{colors.clubhouse-white}"
    textColor: "{colors.practice-night}"
    rounded: "{rounded.lg}"
    padding: "0"
  field:
    backgroundColor: "{colors.clubhouse-white}"
    textColor: "{colors.practice-night}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "44px"
  error-notice:
    backgroundColor: "{colors.error-surface}"
    textColor: "{colors.practice-night}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "16px"
  success-toast:
    backgroundColor: "{colors.practice-night}"
    textColor: "{colors.clubhouse-white}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
---

# Design System: VK Cricket Academy Portal

## Overview

**Creative North Star: "The Disciplined Clubhouse"**

The portal should feel like arriving at a well-run academy before the first session of the day: open, prepared, calm, and focused on the work ahead. Spacious composition and familiar product patterns make the interface welcoming, while dense event details and direct actions keep coaches moving through operational tasks.

This is a product interface, not a sports campaign. It rejects generic corporate dashboards, interchangeable SaaS decoration, sports-betting spectacle, and visual effects that slow down routine work. Cricket identity comes from disciplined structure, the academy teal, relevant language, and the activity itself—not decorative sporting imagery.

**Key Characteristics:**

- Open, event-led dashboard composition with a clear daily briefing.
- Deep-slate navigation that frames, rather than dominates, the workspace.
- Restrained academy teal used for wayfinding, focus, icons, and the inset boundary line.
- Flat white surfaces, fine dividers, and useful density without nested cards.
- Familiar system typography and 44px minimum interactive targets.
- State-resilient workflows that retain useful results, announce changes, and restore focus deliberately.

## Colors

The palette pairs a cool, bright workspace with a deep practice-night sidebar and one disciplined teal brand voice.

### Primary

- **Academy Teal** (`#559eac`): Brand perimeter, focus rings, action borders, and small wayfinding accents. Use dark slate foregrounds when teal is a filled surface.
- **Academy Teal Wash** (`#eef5f7`): A derived 10% teal-on-white state surface for restrained player-type badges and quiet hover feedback.
- **Academy Teal Soft** (`#ddecee`): A derived 20% teal-on-white identity surface reserved for generated initials avatars.

### Neutral

- **Practice Night** (`#0f172a`): Sidebar surface and strongest text.
- **Slate Ink** (`#1e293b`): Secondary headings and strong interface labels.
- **Body Copy** (`#475569`): Supporting descriptions on white and cool-canvas surfaces.
- **Muted Copy** (`#64748b`): Timestamps and tertiary metadata only.
- **Cool Canvas** (`#f8fafc`): Main application background.
- **Clubhouse White** (`#ffffff`): Summary bands, event lists, active navigation, and controls.
- **Boundary Line** (`#e2e8f0`): Dividers and container outlines.
- **Danger Action** (`#991b1b`): Destructive confirmation fills, destructive focus rings, and high-emphasis retry borders.
- **Error Surface** (`#fef2f2`): Non-destructive error and recovery notices paired with dark red or slate copy.
- **Warning Surface** (`#fffbeb`): Conflict, temporary-password, and caution states paired with explicit text.
- **Success Marker** (`#34d399`): A small supporting marker inside the dark success toast; the visible message carries the meaning.

**The Boundary Line Rule.** The sidebar brand line is always a complete 2px perimeter inset 3px from every edge. Never turn it into a one-sided accent stripe.

**The Earned Teal Rule.** Academy teal marks identity, focus, or navigation. It does not replace body text and should remain visually scarce outside the sidebar perimeter.

## Typography

**Display Font:** System UI with platform-native fallbacks  
**Body Font:** System UI with platform-native fallbacks  
**Label Font:** System UI with platform-native fallbacks

**Character:** Familiar, sturdy, and quick to scan. One family carries the complete product UI; hierarchy comes from weight, fixed sizes, and spacing rather than decorative font pairing.

### Hierarchy

- **Headline** (700, 2.25rem desktop / 1.875rem mobile, 1.15): Page greetings and primary route headings.
- **Title** (700, 1.25rem, 1.4): Major dashboard sections.
- **Subheading** (600–700, 1rem, 1.5): Event names, activity types, and summary labels.
- **Body** (400, 1rem, 1.5): Explanatory copy with a preferred maximum line length of 65–75 characters.
- **Label** (600, 0.875rem, 1.25): Navigation, action labels, event metadata, and controls.

**The Operational Scale Rule.** Product typography uses fixed rem sizes with only one mobile-to-desktop headline adjustment. Do not use oversized fluid display type in authenticated workflows.

## Elevation

The system is flat by default. Depth comes from the contrast between cool canvas, white surfaces, deep navigation, and 1px boundary lines. Shadows are omitted from routine dashboard containers; overlays use backdrop contrast rather than decorative elevation.

**The Flat-by-Default Rule.** If spacing, tone, and a 1px divider can explain the hierarchy, do not add a shadow.

## Components

### Buttons

- **Shape:** Restrained rounding (`8px`) with a minimum `44px` height.
- **Quick actions:** White surface, slate text, 1px Academy Teal border, and a teal line icon. Hover uses a light teal wash.
- **Primary actions:** Practice Night fill, white text, and the same restrained `8px` shape. Reserve red fills for confirmed destructive actions.
- **Focus:** A visible 2px Academy Teal ring with 2px offset.
- **Copy:** Direct verb-object labels such as “Add player,” “Create match,” and “Schedule event.”

### Inputs / Fields

- **Style:** Clubhouse White, 1px slate-300 border, `8px` radius, readable slate-900 text, and a minimum `44px` height.
- **Focus:** Shift the border to Academy Teal and add a visible 2px teal ring. Use the softer 40% ring only where the established form field pattern already does so.
- **Labels:** Keep persistent visible labels programmatically associated with their native control. Placeholder copy never replaces a label.
- **Error / Disabled:** Place specific error copy next to the field and connect it with `aria-describedby`. Disabled fields use a slate-100 surface and remain recognizable without color alone.
- **Native controls:** Prefer native selects for short operational lists. Keep canonical values internal while presenting plain-language option labels.

### Cards / Containers

- **Corner Style:** `12px` maximum for dashboard surfaces.
- **Background:** Clubhouse White on Cool Canvas.
- **Shadow Strategy:** None at rest.
- **Border:** 1px Boundary Line.
- **Internal Padding:** `20px` mobile and `24px` desktop.
- **Summary band:** One shared surface split by dividers; never three detached hero-metric cards.

### Profile Cards

- **Density:** Profile summaries are a deliberately compact container class. Use `12px` internal padding, tight `8px` vertical divisions, and a minimum `44px` interaction target without changing the roomier dashboard-surface default.
- **Anatomy:** Keep one readable sequence: initials avatar and identity, player type and role-aware cricket summary, then supporting metadata.
- **Interaction:** The entire card is one accessible details trigger. Use a restrained teal border/background hover, a visible teal focus ring, and no nested actions.
- **Responsiveness:** Let names, team membership, and summaries wrap. Grid column widths are local layout decisions, not design-system tokens.
- **Skeleton:** Initial-loading skeletons must mirror the card's compact anatomy and stop pulsing under reduced-motion preferences.

**The Identity Expansion Rule.** A detail view expands the selected summary; it never invents a second information hierarchy. Preserve identity, team membership, player type, cricket summary, full profile, date of birth, biography, and permitted actions in that order.

### Chips

- **Style:** White background, 1px Academy Teal border, Slate Ink text, `6px` radius.
- **Purpose:** Always pair color with text such as “Training” or “Match.”
- **Player type:** A compact `24px`-minimum badge may use Academy Teal Wash with a 1px Academy Teal border, Slate Ink text, and full labels such as “All-rounder.” The tint supports recognition; the text carries the meaning.

### Identity Avatars

- **Treatment:** Generated initials use Academy Teal Soft, Practice Night text, bold system type, and a full-circle shape.
- **Sizing:** Use `44px` in compact cards and `56px` when the same identity leads a modal.
- **Content:** Compose the first usable character of the first and last names, fall back to one usable initial, then a neutral dash when neither exists.
- **Accessibility:** Mark generated initials decorative. The adjacent visible name remains the authoritative accessible identity.

### Modal Dialogs

- **Primitive:** Use the shared native `<dialog>` rendered through a portal. It provides modal isolation, focus containment, Escape dismissal, scroll locking, backdrop dismissal, and focus restoration.
- **Layering:** Use the semantic overlay order: dropdown (`10`), sticky (`20`), navigation backdrop (`30`), modal backdrop (`40`), modal (`50`), toast (`60`), tooltip (`70`). Never introduce a one-off z-index.
- **Surface:** Clubhouse White, no shadow, no decorative border, `12px` radius, internal scrolling, and small viewport margins. Use a slate backdrop at approximately 60% opacity to establish separation.
- **Heading:** Give the visible `h2` a stable id and connect it with `aria-labelledby`. For player details, the player name itself is the heading; never add a generic “Player details” eyebrow.
- **Initial focus:** Put initial focus on a useful control inside the dialog, normally the close control, and restore focus to the originating trigger on every exit path.
- **Identity continuity:** Reuse the same identity composition and ordering as the summary card, scaling the avatar and title without rearranging the content.
- **Implementation drift:** Add Player and Edit Player still use the legacy custom `role="dialog"` shell and a hard-coded `z-50`. They must migrate to the shared native dialog and semantic overlay tokens; do not treat the legacy shell as a second approved modal pattern.

### Result Collections

- **Initial fetch:** When no prior result set exists, show reduced-motion-safe skeletons that preserve both the summary and collection footprints.
- **Background fetch:** Keep populated results visible, mark the results region `aria-busy="true"`, and update quiet count copy without moving focus.
- **Background error:** Retain the previous results and place a non-destructive error with Retry before them. Name the failed operation as a refresh; reserve load wording for failures with no retained results.
- **Replacement:** Commit only the latest completed request. Never flash an empty state or replace useful content with skeletons during debounce, filtering, pagination refresh, or mutation refresh.

### Operational Filters

- **Structure:** Group filters inside one white, bordered surface. Use native controls, visible labels, equal `44px` heights, and one explicit Clear action.
- **Responsive behavior:** Stack at narrow mobile widths, use a predictable two-column tablet grid, and move to one aligned desktop row only when the content area can support it.
- **Values and labels:** API identifiers remain canonical filter values, but concise academy-facing labels are the visible copy. Presentation metadata stays typed and feature-local.
- **Clear state:** Disable Clear when no filter is active, using cursor, surface, border, and text changes together.

### Status, Error, and Success Feedback

- **Errors:** Use `role="alert"`, plain-language recovery copy, and an explicit Retry action. Initial failures replace unavailable content; refresh failures retain prior content.
- **Severity:** Pair rose, amber, and sky treatments with visible “Critical,” “Warning,” and “Info” text. Color supports scanning but never carries severity alone.
- **Success toast:** Use a compact Practice Night surface, white copy, a visible Dismiss action, and the semantic toast layer (`60`). Automatic dismissal pauses while hovered or while keyboard focus is within the toast, then resumes with the remaining delay.
- **Conflicts:** Close stale confirmations, refresh the underlying result, and move focus to a stable recovery control or the refreshed results region.

### Pagination

- **Targets:** Every arrow and page button is at least `44px` square with visible Academy Teal focus.
- **Current page:** Practice Night fill, white text, and `aria-current="page"`.
- **Narrow screens:** Keep previous and next controls fixed while the page-number strip scrolls horizontally inside its own bounds. Never create document-level horizontal overflow.

### Navigation

- **Sidebar:** Practice Night surface with the full Academy Teal inset perimeter.
- **Brand block:** Temporary square logo, “VK Cricket Academy,” and “Academy Portal” at the top; text collapses on desktop while the logo remains.
- **Items:** White text and line icons, 44px minimum height, subtle white hover wash.
- **Active:** Clubhouse White surface, Practice Night text, and an inset Academy Teal ring.
- **Footer controls:** Icon-only User Settings and collapse/expand controls share one bottom row while expanded. In the collapsed desktop rail, Settings stacks above the chevron so the expand control remains visible at the bottom. Both retain accessible names and tooltips.
- **Mobile:** A modal drawer with focus containment, background isolation, Escape support, and a dedicated close control.
- **Route focus:** On client-side navigation, update the document title and move programmatic focus to the newly rendered route `h1`. Route headings use `tabindex="-1"` so they remain outside the normal Tab sequence.

### Event List

- **Structure:** Date block, flexible event detail, and text category chip.
- **Rhythm:** Rows are separated by 1px lines inside one shared surface.
- **Responsive behavior:** Metadata wraps and the chip moves below details on narrow screens; no horizontal scrolling.

### Activity Timeline

- **Structure:** A single 1px chronological guide with compact filled icon markers.
- **Hierarchy:** Activity title first, detail second, timestamp quiet but readable.

## Do's and Don'ts

### Do:

- **Do** keep routine academy operations fast, direct, and familiar.
- **Do** use `#559eac` for the sidebar perimeter, focus, icons, action borders, and wayfinding.
- **Do** use dark slate text on filled Academy Teal; the pairing exceeds WCAG AA for normal text.
- **Do** preserve complete keyboard operation, visible focus, reduced motion, semantic landmarks, and 44px targets.
- **Do** group related dashboard data into shared bands and lists with 1px dividers.
- **Do** make responsive behavior structural: stack summaries, reflow events, and use the mobile drawer.
- **Do** preserve a player's identity hierarchy as a compact card expands into a detail modal.
- **Do** retain useful content during background fetches and expose progress with `aria-busy`.
- **Do** use the semantic overlay scale and restore focus to the originating trigger when a modal closes.
- **Do** give primary route headings `tabindex="-1"` so shared SPA navigation can announce new content without adding a Tab stop.
- **Do** pause automatically dismissed feedback while it is hovered or contains keyboard focus.
- **Do** expose academy-facing labels while keeping canonical API identifiers in typed internal values.

### Don't:

- **Don't** turn the portal into a generic corporate or interchangeable SaaS dashboard.
- **Don't** use flashy sports-betting aesthetics, neon scoreboards, or spectacle-first visuals.
- **Don't** add decoration that slows routine work or obscures player development.
- **Don't** use one-sided accent stripes; the sidebar line must remain a complete inset perimeter.
- **Don't** use gradient text, glassmorphism, decorative grids, cream backgrounds, or oversized hero metrics.
- **Don't** create identical card grids or nest cards inside other cards.
- **Don't** exceed `12px` corner radii on cards and dashboard surfaces.
- **Don't** rely on Academy Teal for normal-size text on white; use Slate Ink and keep teal for non-text accents.
- **Don't** replace populated collections with skeletons during background work.
- **Don't** add nested actions to a profile card; the card is one details trigger.
- **Don't** create modal-specific heading systems, arbitrary z-index values, or a generic eyebrow above the actual dialog title.
- **Don't** expose backend identifiers as primary interface copy when a concise staff-facing label is available.
- **Don't** move focus during ordinary filtering or background refresh; reserve focus movement for route changes, dialogs, conflicts, and terminal remediation outcomes.
