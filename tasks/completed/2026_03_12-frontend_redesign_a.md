# 2026-03-12 Frontend Stability Redesign

## Status

- Proposed
- Scope: `frontend/` only unless route or docs updates require small top-level doc changes

## Summary

The current frontend feels fragile because the app does not present one durable visual system. Shared primitives, page shell styling, dashboard styling, and agent styling are all pushing in slightly different directions. The result is a UI that feels soft, decorative, and inconsistent instead of precise, grounded, compact, and modern.

This task is a frontend stabilization and design-system reset, not a cosmetic pass. The goal is to make Bill Helper feel like a dependable local-first ledger workspace with AI capabilities, rather than an AI-first prototype wrapped in ad hoc styling.

## Current-State Findings

These findings come from the stable frontend docs and current code, not from prior task proposals.

### Structural findings

- `frontend/src/styles.css` is the main styling hub and currently mixes theme tokens, app shell rules, dashboard rules, properties layout rules, agent panel rules, review modal rules, and shared utility classes in one file.
- Route pages are mostly thin orchestrators already, which is good. Visual inconsistency is coming more from shared styling and page composition than from deeply tangled business logic.
- The home route renders the agent panel directly via `frontend/src/pages/HomePage.tsx`, so the first impression of the app is the most bespoke and least grounded surface.
- Several pages already have stable composition seams that can support a redesign without domain churn:
  - `AccountsPage` is thin and feature-driven.
  - `PropertiesPage` is thin and feature-driven.
  - `SettingsPage` already has a compact sticky toolbar pattern worth reusing.

### Visual findings

- The current theme tokens combine warm neutrals, soft accent surfaces, large radii, and layered shadows. That gives a mild "soft SaaS" feel instead of a solid financial-tool feel.
- The main content canvas uses decorative radial gradients. This weakens the sense of a fixed, trustworthy workspace.
- Cards, buttons, chips, dialogs, and timeline elements default to rounded and slightly floating treatments, so even dense data surfaces inherit a "lightweight prototype" feel.
- There are many tiny uppercase labels, translucent surfaces, muted fills, and pill-like controls. In isolation these are fine, but together they make the interface feel busy and overly styled.
- Dashboard and agent surfaces are visually more bespoke than entries/accounts/properties/settings, which makes the app feel inconsistent across routes.

### Product findings

- Bill Helper is fundamentally a ledger workspace with AI review and AI assistance. The visual hierarchy should communicate "ledger first, AI integrated" even if the AI page remains important.
- The strongest existing UX patterns are the ones that look more operational than decorative:
  - compact table workspaces
  - sticky toolbars
  - dialog-driven edits
  - clear list/detail or list/filter layouts

## Primary Outcome

Create a stable, compact, grounded visual system for the frontend that:

- feels like a serious local-first finance tool
- supports high-density data work without feeling cramped
- makes AI features feel integrated into the product instead of visually detached from it
- reduces styling fragility by moving from one-off visual decisions to shared tokens and reusable layout primitives

## Design Direction

Adopt a "ledger workstation" visual language.

That means:

- neutral, solid surfaces instead of decorative backgrounds
- restrained color with one primary accent and disciplined semantic tones
- compact, information-dense spacing
- strong borders and hierarchy instead of blur and softness
- consistent workspace chrome across all routes
- motion used sparingly and only where it improves orientation

## UX Goals

- Grounded: the app should feel stable, trustworthy, and quiet.
- Consistent: moving between Dashboard, Entries, Accounts, Properties, Settings, and Agent should feel like moving between workspaces in the same product.
- Compact: controls and cards should support real data work instead of oversized demo spacing.
- Modern: the app should still feel current, but through clarity, rhythm, and typography rather than trendy effects.
- Durable: small UI changes should happen by editing tokens or shared components, not by adding more local exceptions.

## Non-Goals

- No backend API or domain-model changes.
- No router/service ownership changes outside normal frontend composition work.
- No large new tooling adoption such as Storybook, Percy, or a design-token build pipeline in this task.
- No broad interaction redesign of ledger workflows unless a visual cleanup exposes a clear usability defect that can be fixed locally.
- No compatibility shims to preserve obsolete styling patterns. Replace weak patterns when the new system is ready.

## Visual System Specification

### Palette

Use a restrained neutral-first palette.

- Canvas: light neutral, slightly warm or slate-tinted, but solid.
- Panels and cards: near-white solid surfaces with subtle contrast from the canvas.
- Primary accent: one deep, desaturated accent color suitable for a finance tool.
  - Recommended direction: ink blue, iron blue, or dark teal.
- Semantic colors:
  - success for positive money states
  - warning for caution or review-needed states
  - destructive for delete/apply-failure states
- Chart colors should be derived from the same restrained system, not from a separate vivid palette.

Avoid:

- radial gradient page backgrounds
- "glass" styling
- large areas of translucent muted fills
- unrelated accent colors competing on the same screen

### Typography

Recommended direction:

- body and UI font: `IBM Plex Sans` or `Public Sans`
- numeric and code-adjacent values: tabular figures enabled by default; optional mono companion only for highly technical metadata

Typography rules:

- Use fewer all-caps labels.
- Prefer sentence case section labels unless the label is truly meta UI.
- Make page titles and section titles more explicit, but reduce decorative micro-labels.
- Amounts, totals, and tabular data should use tabular numerals and right-aligned layout where appropriate.

### Shape and depth

- Card radius: 8-10px
- Control radius: 6-8px
- Pills/chips: reserved for tags, statuses, and compact filters only
- Use one default shadow level for elevated surfaces and one stronger level for dialogs/dropdowns
- Most surfaces should read through border, contrast, and spacing rather than shadow

### Density

Adopt a compact density scale:

- control height: 36-40px
- table row height: 44-48px
- standard gap scale: 8 / 12 / 16 / 20 / 24
- page padding: slightly reduced from current large-card spacing
- chart and metric cards: smaller headers and tighter body spacing

### Motion

- Keep transitions short and structural: open/close, active-state, selected-state, panel resize feedback
- Remove decorative motion and anything that makes the UI feel floaty
- Preserve smoothness on high-value interactions only:
  - sidebar collapse
  - thread rail open/close
  - dialog open/close
  - dashboard time selection state changes

## App-Specific Design Recommendations

### App shell and sidebar

The shell should communicate "workspace" first.

- Make the sidebar feel like a fixed tool rail, not a soft card.
- Use a solid background and stronger border separation from the content canvas.
- Tighten nav spacing and reduce softness in active states.
- Use one clear active treatment:
  - stronger background contrast
  - left rule or inset marker
  - stronger text/icon color
- Reduce footer copy styling noise. The principal switcher should feel operational, not promotional.

### Home route and agent positioning

The current home route goes directly into the agent panel. That makes the least grounded surface the default face of the app.

Recommended implementation stance for this task:

- Do not change the route structure immediately.
- Keep the current route map unless product direction explicitly changes.
- Redesign the home route so the agent surface inherits the same page-shell discipline as the rest of the app.

Explicit product decision to evaluate during implementation:

1. Keep `/` as the AI page, but wrap it in the same workspace chrome and visual language as the other routes.
2. Move the default landing experience to `Dashboard` or `Entries`, and make the agent a first-class workspace rather than the default home.

Recommendation:

- Start with option 1 so the redesign can proceed without route churn.
- Revisit option 2 only after the new visual system is in place and the product team decides whether Bill Helper should remain AI-home-first.

### Entries, Accounts, Entities, Groups, Properties, Filter

These routes should become the visual baseline for the product.

- Standardize a shared page template:
  - page header
  - optional toolbar/filter row
  - primary data surface
  - secondary dialogs or side panels
- Use one table-shell pattern across all data-heavy workspaces.
- Align empty states, error states, action placement, search inputs, and filter rows.
- Prioritize dense clarity over decorative framing.
- Keep row actions compact and secondary until destructive confirmation.

### Settings

Settings is already close to the right interaction model.

- Keep the sticky toolbar pattern.
- Use Settings as the first full-page reference implementation for the new design system.
- Make tab states, save-state messaging, and section cards calmer and more aligned with the new visual contract.

### Dashboard

The dashboard should feel analytical, not ornamental.

- Preserve the current information architecture unless a specific layout issue forces change.
- Reduce the visual novelty of the floating right-side timeline rail.
- Restyle month/year selection so it feels anchored and tool-like rather than like floating chips.
- Reduce chart palette noise and unify chart card structure.
- Keep overview metrics compact and comparable.
- Make tables and numeric summaries carry more weight than color blocks.

### Agent panel and review modal

The AI surfaces need the most visual discipline.

- Treat the agent page as part of the same product, not as a separate themed application.
- Reduce bespoke pill, blur, and soft-panel styling across:
  - thread rail
  - timeline bubbles
  - composer
  - review modal
- Make the composer feel like a stable input dock.
- Make the thread rail read like a durable secondary navigation panel.
- Make the review modal read like an operations console:
  - clearer hierarchy
  - denser TOC rows
  - less decorative status styling
  - stronger distinction between pending, approved, applied, rejected, and failed

## Technical Implementation Plan

### Phase 0: Establish the visual contract

- Produce a short design brief inside implementation notes before changing multiple screens.
- Decide:
  - primary font direction
  - primary accent color direction
  - radius scale
  - default control heights
  - whether `/` remains the long-term home route
- Create a before/after checklist covering:
  - sidebar
  - page header
  - table workspace
  - form workspace
  - dashboard
  - agent panel
  - review modal

Exit criteria:

- One agreed visual contract exists before mass migration begins.

### Phase 1: Rebuild the theme and shared primitives

- Replace the current soft token set with a stricter semantic token system.
- Refactor shared primitives first:
  - `Button`
  - `Card`
  - `Input`
  - `Textarea`
  - `Select`
  - `Badge`
  - `Table`
  - `Dialog`
- Introduce tabular figure treatment for numeric UI.
- Remove decorative defaults from primitives so pages stop inheriting softness automatically.

Recommended token groups:

- canvas/background
- panel/surface
- muted surface
- foreground/default
- foreground/muted
- border/default
- border/strong
- accent/default
- accent/foreground
- semantic success/warning/destructive
- radius scale
- elevation scale

Exit criteria:

- Shared components can render a stable compact surface without page-specific overrides.

### Phase 2: Split style ownership into durable layers

The current single-file styling approach is too broad.

Refactor styling into a small number of durable layers, for example:

- `frontend/src/styles.css` as the import/root layer only
- `frontend/src/styles/tokens.css`
- `frontend/src/styles/base.css`
- `frontend/src/styles/shell.css`
- `frontend/src/styles/workspaces.css`
- `frontend/src/styles/agent.css`

Rules:

- Keep the number of files small and durable.
- Do not create one CSS file per page.
- Shared workspace patterns belong in shared style modules.
- Feature-specific styling belongs close to the feature only when it is truly feature-specific.

Exit criteria:

- Styling ownership is understandable and no single CSS file acts as the entire app's dumping ground.

### Phase 3: Introduce shared layout primitives

Add or formalize layout components that pages can share.

Recommended additions:

- `PageHeader`
- `WorkspaceSection`
- `WorkspaceToolbar`
- `DataSurface`
- `MetricRow` or `StatBlock`
- `EmptyState`
- `InlineStatusMessage`

Rules:

- Route pages remain thin composition shells.
- Shared layout components own visual structure, not domain logic.
- Do not duplicate toolbar and card chrome across pages.

Exit criteria:

- Entries, Accounts, Properties, Settings, and Filter can use the same layout vocabulary.

### Phase 4: Migrate reference workspaces first

Migration order:

1. Settings
2. Entries
3. Accounts
4. Entities / Groups / Properties / Filter

Why this order:

- Settings has the cleanest current shell pattern.
- Entries and Accounts represent the core ledger work experience.
- The remaining CRUD-heavy workspaces can then converge on the same table and dialog patterns.

Exit criteria:

- Core ledger workspaces feel like one system before dashboard and agent are restyled.

### Phase 5: Restyle Dashboard

- Keep the current feature set and data behavior stable.
- Rebuild dashboard cards, metrics, chart shells, and the time selector using the new primitives.
- Reduce visual drift between dashboard and the rest of the app.
- Ensure chart components follow the same spacing, heading, border, and state treatment as data tables and forms.

Exit criteria:

- Dashboard feels analytical and operational instead of special-case and decorative.

### Phase 6: Restyle Agent and review surfaces

- Rework agent shell styling after the rest of the system is stable.
- Reuse page-header, panel, toolbar, and status primitives where possible.
- Keep existing agent architecture seams intact:
  - `AgentPanel`
  - `panel/*`
  - `review/*`
- Focus on visual simplification and shared hierarchy, not on changing orchestration ownership.

Exit criteria:

- The AI workspace feels fully integrated into the product's visual system.

### Phase 7: Polish, cleanup, and documentation sync

- Remove unused classes and stale visual exceptions.
- Update frontend docs to describe the new styling system and page chrome.
- Confirm that no old soft-theme assumptions remain in shared primitives.

Exit criteria:

- The redesign is documented and the old styling debt is materially reduced.

## Concrete File Targets

Expected primary touch points:

- `frontend/src/styles.css`
- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/textarea.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/table.tsx`
- `frontend/src/components/ui/badge.tsx`
- `frontend/src/components/ui/dialog.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/App.tsx`
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/EntriesPage.tsx`
- `frontend/src/pages/AccountsPage.tsx`
- `frontend/src/pages/PropertiesPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/features/settings/SettingsToolbar.tsx`
- `frontend/src/features/agent/AgentPanel.tsx`
- `frontend/src/features/agent/panel/*`
- `frontend/src/features/agent/review/*`

## Acceptance Criteria

### Visual criteria

- The app no longer uses decorative gradient page backgrounds for normal workspace routes.
- Shared surfaces use a consistent radius, border, and shadow language.
- Data-heavy pages feel denser and calmer.
- The sidebar, table workspaces, dashboard, and agent page clearly belong to the same product.
- Numeric data reads more clearly through alignment, spacing, and typography.

### Architecture criteria

- Shared styling rules are no longer concentrated in a single oversized catch-all file.
- Shared primitives own the default visual language.
- Route pages remain thin.
- No new page-specific styling hacks are introduced to compensate for weak primitives.

### Product criteria

- The app feels trustworthy and operational within the first few seconds of use.
- AI capabilities feel integrated rather than visually detached.
- Mobile layouts still work and do not rely on desktop-only composition assumptions.

## Verification Plan

Implementation verification for this task should include:

- `npm run test` in `frontend/`
- `npm run build` in `frontend/`
- `uv run python scripts/check_docs_sync.py`

Manual QA should explicitly cover:

- desktop at approximately 1280px and 1440px widths
- small laptop height constraints
- mobile width around 390px
- sidebar collapsed and expanded states
- dashboard month/year selector behavior
- agent thread rail open/close and resize behavior
- dialog readability and focus treatment
- table density and overflow behavior

## Documentation Updates Required During Implementation

When the redesign is implemented, update the stable docs that describe current behavior:

- `frontend/docs/styles_and_operations.md`
- `frontend/docs/app_shell_and_routing.md`
- `frontend/docs/workspaces.md`
- `frontend/docs/agent_workspace.md`
- `docs/frontend_index.md` if the stable frontend doc map changes
- `docs/features/dashboard_analytics.md` only if dashboard interaction or information architecture changes materially

## Risks And Mitigations

### Risk: big-bang repaint without a stable system

Mitigation:

- lock the visual contract first
- rebuild primitives before migrating pages
- use Settings and Entries as early reference surfaces

### Risk: dashboard and agent continue to feel like separate applications

Mitigation:

- postpone their restyle until shared primitives and workspace chrome are stable
- then migrate them using the same system instead of inventing route-specific styling

### Risk: compact redesign becomes cramped

Mitigation:

- define explicit density targets
- verify numeric readability and input hit areas
- keep clear section rhythm even while reducing padding

### Risk: CSS refactor becomes over-engineered

Mitigation:

- keep the new style structure small
- split by durable ownership layers, not by every route

## Recommended Definition Of Done

This task is done when:

- Bill Helper reads as one stable product across all major routes
- the visual system feels compact and grounded without becoming dull or dated
- styling changes can be made by editing shared tokens and primitives instead of chasing one-off classes
- the home route no longer undermines first impression quality
- frontend docs are updated to describe the new current state
