---
name: VK Cricket Academy Portal
description: An open, disciplined operations interface for academy coaches and players.
colors:
  academy-teal: "#559eac"
  practice-night: "#0f172a"
  slate-ink: "#1e293b"
  body-copy: "#475569"
  muted-copy: "#64748b"
  cool-canvas: "#f8fafc"
  clubhouse-white: "#ffffff"
  boundary-line: "#e2e8f0"
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

## Colors

The palette pairs a cool, bright workspace with a deep practice-night sidebar and one disciplined teal brand voice.

### Primary

- **Academy Teal** (`#559eac`): Brand perimeter, focus rings, action borders, and small wayfinding accents. Use dark slate foregrounds when teal is a filled surface.

### Neutral

- **Practice Night** (`#0f172a`): Sidebar surface and strongest text.
- **Slate Ink** (`#1e293b`): Secondary headings and strong interface labels.
- **Body Copy** (`#475569`): Supporting descriptions on white and cool-canvas surfaces.
- **Muted Copy** (`#64748b`): Timestamps and tertiary metadata only.
- **Cool Canvas** (`#f8fafc`): Main application background.
- **Clubhouse White** (`#ffffff`): Summary bands, event lists, active navigation, and controls.
- **Boundary Line** (`#e2e8f0`): Dividers and container outlines.

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
- **Focus:** A visible 2px Academy Teal ring with 2px offset.
- **Copy:** Direct verb-object labels such as “Add player,” “Create match,” and “Schedule event.”

### Cards / Containers

- **Corner Style:** `12px` maximum for dashboard surfaces.
- **Background:** Clubhouse White on Cool Canvas.
- **Shadow Strategy:** None at rest.
- **Border:** 1px Boundary Line.
- **Internal Padding:** `20px` mobile and `24px` desktop.
- **Summary band:** One shared surface split by dividers; never three detached hero-metric cards.

### Chips

- **Style:** White background, 1px Academy Teal border, Slate Ink text, `6px` radius.
- **Purpose:** Always pair color with text such as “Training” or “Match.”

### Navigation

- **Sidebar:** Practice Night surface with the full Academy Teal inset perimeter.
- **Brand block:** Temporary square logo, “VK Cricket Academy,” and “Academy Portal” at the top; text collapses on desktop while the logo remains.
- **Items:** White text and line icons, 44px minimum height, subtle white hover wash.
- **Active:** Clubhouse White surface, Practice Night text, and an inset Academy Teal ring.
- **Footer controls:** Icon-only User Settings and collapse/expand controls share one bottom row while expanded. In the collapsed desktop rail, Settings stacks above the chevron so the expand control remains visible at the bottom. Both retain accessible names and tooltips.
- **Mobile:** A modal drawer with focus containment, background isolation, Escape support, and a dedicated close control.

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

### Don't:

- **Don't** turn the portal into a generic corporate or interchangeable SaaS dashboard.
- **Don't** use flashy sports-betting aesthetics, neon scoreboards, or spectacle-first visuals.
- **Don't** add decoration that slows routine work or obscures player development.
- **Don't** use one-sided accent stripes; the sidebar line must remain a complete inset perimeter.
- **Don't** use gradient text, glassmorphism, decorative grids, cream backgrounds, or oversized hero metrics.
- **Don't** create identical card grids or nest cards inside other cards.
- **Don't** exceed `12px` corner radii on cards and dashboard surfaces.
- **Don't** rely on Academy Teal for normal-size text on white; use Slate Ink and keep teal for non-text accents.
