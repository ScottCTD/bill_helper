# Frontend Theme & Visual Overhaul

## Problem

The frontend looks vibe-coded: warm/sandy, bubbly, inconsistent, and ungrounded.
The root causes are a warm-tinted color palette, oversized border radii, noisy
gradient backgrounds, a 2660-line monolith CSS file mixing concerns, and
inconsistent use of component primitives across pages.

This plan fixes the visual identity first (high impact, low effort), then
addresses the structural CSS problems that make the UI feel fragile.

## Diagnosis

### 1. Warm color palette reads as "craft project"

The light theme uses hues 32–35 (tan/beige) for every neutral surface:

```css
--secondary: 35 25% 94%;   /* warm sand */
--muted: 35 22% 95%;       /* warm sand */
--accent: 34 22% 92%;      /* warm sand */
--border: 32 11% 82%;      /* warm sand */
--input: 32 12% 84%;       /* warm sand */
--ring: 32 28% 42%;        /* warm brown */
```

Modern "grounded" apps (Linear, Vercel, Notion, Stripe, Raycast) use neutral
gray or cool-gray: hue 0 or 210–220 with saturation ≤15%. Warm tints make the
UI feel handmade rather than engineered.

### 2. Light and dark themes have different personalities

Light = warm/sandy (hue ~32). Dark = cool/blue (hue ~217). Switching themes
feels like switching apps. Both should share the same hue family.

### 3. Border radius is too large

```css
--radius: 0.9rem;
```

Combined with `rounded-2xl` on cards (which maps to 1rem), everything looks
like a bubble. The shadcn `Card` component hardcodes `rounded-2xl`:

```tsx
// card.tsx
"rounded-2xl border border-border/85 bg-card ..."
```

Modern solid UIs use 0.375rem–0.5rem for the base radius. Cards at `rounded-lg`
(0.5rem) feel intentional; at `rounded-2xl` (1rem) they feel inflated.

### 4. Gradient background adds visual noise

```css
.app-main-padded {
  background:
    radial-gradient(circle at top left, hsl(var(--accent) / 0.9), transparent 24rem),
    radial-gradient(circle at top right, hsl(var(--success) / 0.09), transparent 20rem),
    linear-gradient(180deg, hsl(var(--muted) / 0.45), hsl(var(--background)));
}
```

Three layered gradients with colored tints. Grounded apps use a flat muted
background or at most a single subtle vertical fade.

### 5. Notification toasts hardcode colors outside the theme

```css
.notification-toast { ... bg-white/[0.88] ... text-slate-900 ... }
.notification-toast-success { ... bg-emerald-50/[0.88] ... }
.notification-toast-error { ... bg-rose-50/90 ... }
```

These bypass CSS variables entirely, so they won't follow theme changes and
they clash with the rest of the palette.

### 6. Tooltip hardcodes colors outside the theme

```css
.tooltip-content { ... border-slate-200/80 bg-white/95 ... text-slate-700 ... }
```

Same problem as notifications — hardcoded Tailwind colors instead of theme vars.

### 7. Shadow colors are hardcoded to a specific hue

```css
/* card.tsx */
shadow-[0_1px_1px_hsl(222_18%_19%_/_0.02),0_10px_28px_hsl(222_18%_19%_/_0.05)]

/* .agent-composer-box */
shadow-[0_1px_3px_hsl(222_18%_19%_/_0.04),0_4px_12px_hsl(222_18%_19%_/_0.06)]
```

These use `hsl(222 18% 19%)` which is fine for the dark-foreground theme but
won't adapt if the foreground hue changes. Should use `var(--foreground)`.

### 8. Inconsistent spacing and composition across pages

| Page | Wrapper | Spacing | Title style |
|------|---------|---------|-------------|
| EntriesPage | `Card > CardContent space-y-4 pt-6` | space-y-4 | `.table-shell-title` (text-lg) |
| EntitiesPage | `Card > CardContent space-y-4 pt-6` | space-y-4 | `.table-shell-title` (text-lg) |
| PropertiesPage | `Card > CardContent space-y-5 pt-6` | space-y-5 | inline `text-xl font-semibold` |
| AccountsPage | `stack-lg` wrapper, no Card | gap-6 | `.table-shell-title` (text-lg) |
| DashboardPage | `Card > CardContent space-y-4 pt-6` | space-y-4 | `.table-shell-title` (text-lg) |

Different pages use different spacing (`space-y-4` vs `space-y-5` vs `gap-6`),
different title sizes, and different wrapping strategies.

### 9. Duplicate card styling

The `.card` CSS class and the `<Card>` shadcn component both exist and define
slightly different styles:

```css
/* styles.css .card class */
@apply rounded-2xl border border-border/85 bg-card px-5 py-5
  shadow-[0_1px_1px_hsl(222_18%_19%_/_0.02),0_10px_30px_hsl(222_18%_19%_/_0.04)];

/* card.tsx <Card> component */
"rounded-2xl border border-border/85 bg-card text-card-foreground
  shadow-[0_1px_1px_hsl(222_18%_19%_/_0.02),0_10px_28px_hsl(222_18%_19%_/_0.05)]"
```

Different shadow spread (30px vs 28px), different opacity (0.04 vs 0.05), one
has padding, one doesn't. Pages mix both approaches.

### 10. 2660-line styles.css monolith

The file contains base resets, theme variables, app shell layout, sidebar,
dashboard, entries table, groups browser, group detail modal, entry editor,
agent panel, agent timeline, agent composer, agent review modal, notifications,
tooltips, and more — all in one file. This makes it hard to reason about what
styles affect what, and easy to introduce conflicts.

---

## Plan

### Phase 1 — Theme variables (30 min, transforms the entire feel)

Replace the light-mode CSS variables in `styles.css` `:root` with a neutral
cool-gray palette. Align the dark-mode palette to the same hue family.
Drop `--radius` from `0.9rem` to `0.5rem`.

#### Light theme target values

```css
:root {
  --background: 0 0% 100%;
  --foreground: 224 12% 14%;
  --card: 0 0% 100%;
  --card-foreground: 224 12% 14%;
  --popover: 0 0% 100%;
  --popover-foreground: 224 12% 14%;
  --primary: 221 44% 26%;
  --primary-foreground: 210 40% 98%;
  --secondary: 220 14% 96%;
  --secondary-foreground: 224 12% 18%;
  --muted: 220 14% 96%;
  --muted-foreground: 220 9% 46%;
  --accent: 220 14% 94%;
  --accent-foreground: 224 12% 14%;
  --destructive: 0 72% 51%;
  --destructive-foreground: 0 0% 98%;
  --border: 220 13% 91%;
  --input: 220 13% 91%;
  --ring: 221 44% 26%;
  --success: 152 56% 40%;
  --success-foreground: 152 56% 16%;
  --warning: 36 82% 46%;
  --warning-foreground: 36 92% 12%;
  --radius: 0.5rem;
}
```

Key changes:
- All neutral hues moved to ~220 (cool gray) with saturation 9–14%
- Primary is a deep navy instead of warm dark
- Ring matches primary for consistent focus indicators
- Radius drops from 0.9rem to 0.5rem

#### Dark theme target values

```css
.dark {
  --background: 224 18% 10%;
  --foreground: 210 40% 96%;
  --card: 224 18% 13%;
  --card-foreground: 210 40% 96%;
  --popover: 224 18% 13%;
  --popover-foreground: 210 40% 96%;
  --primary: 213 94% 68%;
  --primary-foreground: 224 18% 10%;
  --secondary: 223 16% 20%;
  --secondary-foreground: 210 40% 96%;
  --muted: 223 16% 18%;
  --muted-foreground: 218 15% 65%;
  --accent: 223 18% 22%;
  --accent-foreground: 210 40% 96%;
  --destructive: 0 72% 56%;
  --destructive-foreground: 0 0% 98%;
  --border: 223 14% 24%;
  --input: 223 14% 24%;
  --ring: 213 94% 68%;
  --success: 152 48% 47%;
  --success-foreground: 152 62% 88%;
  --warning: 36 92% 52%;
  --warning-foreground: 36 92% 14%;
}
```

Key change: hue family is now 223–224 in both themes (was 32–35 light, 217–219
dark). Switching themes feels like the same app in a different room, not a
different app.

#### Files to edit

- `frontend/src/styles.css` — replace `:root` and `.dark` variable blocks

### Phase 2 — Flatten background, tighten radii (15 min)

#### 2a. Flatten the page background

In `styles.css`, replace the `.app-main-padded` background:

```css
/* Before */
background:
  radial-gradient(circle at top left, hsl(var(--accent) / 0.9), transparent 24rem),
  radial-gradient(circle at top right, hsl(var(--success) / 0.09), transparent 20rem),
  linear-gradient(180deg, hsl(var(--muted) / 0.45), hsl(var(--background)));

/* After */
background: hsl(var(--muted));
```

A flat muted surface. Content cards sit on top with their white background and
subtle shadow — this is the Linear/Notion pattern.

#### 2b. Tighten card border radius

In `frontend/src/components/ui/card.tsx`, change `rounded-2xl` to `rounded-xl`:

```tsx
// Before
"rounded-2xl border border-border/85 bg-card ..."

// After
"rounded-xl border border-border/85 bg-card ..."
```

With `--radius: 0.5rem`, `rounded-xl` (0.75rem) gives cards a crisp but not
harsh edge. Inner elements using `rounded-lg` (0.5rem) and `rounded-md`
(0.375rem) will nest cleanly.

Also update the `.card` CSS class in `styles.css` from `rounded-2xl` to
`rounded-xl` to keep them in sync.

#### 2c. Tighten radii across styles.css

Search `styles.css` for `rounded-2xl` and replace with `rounded-xl` in these
classes:

- `.sidebar-session-card` — `rounded-xl` → `rounded-lg`
- `.dashboard-month-chip` — `rounded-2xl` → `rounded-xl`
- `.dashboard-month-chip-active` — no change needed (inherits)
- `.dashboard-view-toggle` — `rounded-xl` → `rounded-lg`
- `.agent-panel` — `rounded-2xl` → `rounded-xl`
- `.agent-composer-box` — `rounded-2xl` → `rounded-xl`
- `.groups-detail-section` — `rounded-2xl` → `rounded-xl`
- `.settings-toolbar` — `rounded-2xl` → `rounded-xl`

The pattern: outer containers go from `2xl` → `xl`, inner elements go from
`xl` → `lg`. This creates a consistent 0.75rem / 0.5rem / 0.375rem nesting.

#### Files to edit

- `frontend/src/styles.css` — background + radius changes
- `frontend/src/components/ui/card.tsx` — card radius

### Phase 3 — Fix hardcoded colors (20 min)

#### 3a. Notification toasts

Replace hardcoded Tailwind colors with theme variables:

```css
/* Before */
.notification-toast {
  ... bg-white/[0.88] ... text-slate-900
    shadow-[0_12px_40px_hsl(220_25%_18%_/_0.16)] ...
}

/* After */
.notification-toast {
  ... bg-popover/[0.92] ... text-popover-foreground
    shadow-[0_12px_40px_hsl(var(--foreground)_/_0.12)] ...
}
```

Same for `.notification-toast-success`, `.notification-toast-error`,
`.notification-toast-icon`, `.notification-toast-title`,
`.notification-toast-description`, `.notification-toast-dismiss`.

#### 3b. Tooltip

```css
/* Before */
.tooltip-content {
  ... border-slate-200/80 bg-white/95 ... text-slate-700
    shadow-[0_10px_30px_hsl(220_22%_20%_/_0.14)] ...
}

/* After */
.tooltip-content {
  ... border-border/80 bg-popover/95 ... text-popover-foreground
    shadow-[0_10px_30px_hsl(var(--foreground)_/_0.10)] ...
}
```

#### 3c. Shadow colors in card.tsx and styles.css

Replace `hsl(222 18% 19% / ...)` with `hsl(var(--foreground) / ...)` in:

- `card.tsx` shadow
- `.card` class shadow
- `.agent-composer-box` shadow
- `.entry-editor-sheet` shadow
- `.agent-panel` shadow

#### Files to edit

- `frontend/src/styles.css` — notification, tooltip, shadow fixes
- `frontend/src/components/ui/card.tsx` — shadow color

### Phase 4 — Standardize page composition (45 min)

This phase addresses the inconsistent spacing and wrapping across pages.

#### 4a. Define a page header pattern

Every data page should follow:

```tsx
<div className="stack-lg">
  <div className="section-header">
    <div>
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
    </div>
    {actions}
  </div>
  {/* page content */}
</div>
```

No wrapping `<Card>` around the page header — the header sits directly on the
muted background. Data tables and charts go inside `<Card>` components.

#### 4b. Standardize spacing

Replace all `space-y-4`, `space-y-5` page-level spacing with `stack-lg`
(gap-6) for consistency. Use `stack-sm` (gap-4) inside cards.

#### 4c. Remove the `.card` CSS class

Delete the `.card` class from `styles.css`. Audit all usages and replace with
the `<Card>` component. This eliminates the duplicate styling.

#### Files to edit

- `frontend/src/styles.css` — remove `.card` class
- `frontend/src/pages/EntriesPage.tsx` — standardize layout
- `frontend/src/pages/EntitiesPage.tsx` — standardize layout
- `frontend/src/pages/AccountsPage.tsx` — standardize layout
- `frontend/src/pages/PropertiesPage.tsx` — standardize layout
- `frontend/src/pages/GroupsPage.tsx` — standardize layout
- `frontend/src/pages/DashboardPage.tsx` — standardize layout
- `frontend/src/pages/SettingsPage.tsx` — standardize layout
- `frontend/src/pages/FilterGroupsPage.tsx` — standardize layout

### Phase 5 — Split the CSS monolith (1–2 hours, structural)

Break `styles.css` into focused files. The split follows the existing logical
sections already visible in the file:

```
src/styles/
├── base.css              # @tailwind directives, :root vars, .dark vars,
│                         # html/body resets, scrollbar, typography, form
│                         # element resets, table base styles
├── layout.css            # .app-shell, .sidebar-*, .app-main-*, .app-content,
│                         # .panel-resize-handle, .page, .stack-*, .grid-*,
│                         # .section-header, responsive shell breakpoints
├── components.css        # .card (if kept), .field, .form-grid, .table-shell-*,
│                         # .table-toolbar-*, .controls-inline, .filter-row,
│                         # .secondary-button, .link-button, .key-value-list,
│                         # .kind-indicator-*, .muted, .error
├── entries.css           # .entries-table, .entries-*-column, .entries-name-*,
│                         # .entries-amount-*, .entries-tag-*
├── dashboard.css         # .dashboard-tab-*, .dashboard-page-layout,
│                         # .dashboard-view-toggle-*, .dashboard-timeline-*,
│                         # .dashboard-month-*, .dashboard-comparison-*,
│                         # .dashboard-scope-note, .dashboard-delta-*
├── groups.css            # .groups-browser-*, .groups-detail-*, .groups-empty-*,
│                         # .group-flow-*
├── settings.css          # .settings-tab-*, .settings-reset-*, .settings-toolbar-*
├── entry-editor.css      # .entry-editor-*, .entry-property-*
├── select.css            # .single-select-*, .creatable-select-*,
│                         # .tag-multiselect-*, .tag-chip-*, .tag-option-*
├── agent.css             # .agent-panel-*, .agent-thread-*, .agent-message-*,
│                         # .agent-markdown-*, .agent-run-*, .agent-tool-call-*,
│                         # .agent-review-*, .agent-composer-*, .agent-draft-*,
│                         # .agent-resize-handle
└── notifications.css     # .notification-viewport, .notification-toast-*,
                          # .tooltip-root, .tooltip-content-*
```

The main `styles.css` becomes:

```css
@import "./styles/base.css";
@import "./styles/layout.css";
@import "./styles/components.css";
@import "./styles/entries.css";
@import "./styles/dashboard.css";
@import "./styles/groups.css";
@import "./styles/settings.css";
@import "./styles/entry-editor.css";
@import "./styles/select.css";
@import "./styles/agent.css";
@import "./styles/notifications.css";
```

This is a pure file-organization refactor — no class names change, no behavior
changes. Each file is independently readable and maps to a clear UI domain.

#### Files to create

- `frontend/src/styles/*.css` (11 files)

#### Files to edit

- `frontend/src/styles.css` — replace contents with imports

---

## Execution order

| Phase | Effort | Risk | Impact | Dependencies |
|-------|--------|------|--------|--------------|
| 1. Theme variables | 30 min | Low — CSS-only | **Huge** — kills the craft feel | None |
| 2. Background + radii | 15 min | Low — CSS + 1 component | **Large** — feels tighter | Phase 1 |
| 3. Hardcoded colors | 20 min | Low — CSS + 1 component | **Medium** — theme-consistent | Phase 1 |
| 4. Page composition | 45 min | Medium — touches all pages | **Medium** — consistent layout | Phases 1–2 |
| 5. CSS split | 1–2 hr | Low — pure reorganization | **Structural** — maintainability | Phases 1–3 |

Phases 1–3 can be done in a single session (~1 hour) and will transform the
visual feel. Phase 4 is a follow-up that standardizes layout. Phase 5 is a
housekeeping task that can happen any time after phases 1–3.

## Verification

After each phase:

1. `cd frontend && npm run build` — confirm no build errors
2. Visual check in browser: light mode, dark mode, responsive (narrow viewport)
3. `OPENROUTER_API_KEY=test uv run pytest backend/tests -q` — backend unaffected
4. `uv run python scripts/check_docs_sync.py` — docs sync check

After phase 5 (CSS split), also confirm:

5. `npx vitest run` — frontend tests still pass
6. Diff the rendered CSS output to confirm no class changes
