---
name: notion-grade-ui
description: Enforce a cohesive calm, content-first, Notion-like UI system for this repository's frontend. Use when adding or modifying pages, components, layouts, navigation, forms, tables, dialogs, menus, toasts, or when ad-hoc styles/raw controls appear. Apply token-only styling, primitives-first component usage, subtle interactions, and accessibility checks. Do not use for pure backend changes or explicitly labeled design-system bypass experiments.
---

# Objective

Deliver frontend changes that feel consistent, readable, and intentional by default.

# Hard Requirements

1. Use tokens only.
- Do not hardcode hex colors in component code.
- Do not use arbitrary spacing/radius values unless first added to scale/tokens.
- Source colors, radii, shadows, and typography from tokens/theme variables.

2. Prefer primitives first.
- Do not ship new UI with bespoke styling on raw form controls.
- Reuse or extend shared primitives such as `Button`, `IconButton`, `Input`, `Textarea`, `Select`, `Checkbox`, `Switch`, `Tabs`, `Tooltip`, `Popover`, `Dialog`, `DropdownMenu`, `Toast`, `Table`, `Badge`, `Skeleton`, `Separator`.

3. Ensure interaction quality.
- Provide subtle hover/active states.
- Include crisp visible focus rings.
- Include disabled and loading states.
- Keep motion short and restrained.

4. Meet accessibility baseline.
- Keep all controls keyboard navigable.
- Ensure overlays/menus/dialogs have proper ARIA semantics.
- Maintain acceptable contrast in light and dark modes.

5. Follow layout conventions.
- Prefer app-shell pattern: sidebar + top bar + content canvas.
- Default to readable content width unless dense dashboards need full width.

# Workflow

1. Detect existing stack and patterns in the touched area.
- Locate token/theme source, primitive library location, and current layout/routing conventions.

2. Run a local UI audit before editing.
- Identify inconsistencies in spacing, typography, borders, hover/focus behavior, icon sizing, empty/error states, and table density.

3. Update tokens first when new values are needed.
- Add scale entries centrally before consuming them.

4. Add or extend primitives before screen-level one-offs.
- Turn repeated styling patterns into primitive variants.

5. Apply primitives and standardized tokens to the changed feature.
- Keep spacing rhythm and typography consistent across the touched area.

6. Run behavior and a11y checks.
- Verify keyboard flow (`Tab`, `Enter`, `Escape`).
- Verify focus ring visibility and disabled/loading behavior.

7. Run visual QA.
- Compare density before/after.
- Validate light and dark modes.
- Validate empty/error states.
- Confirm no ad-hoc styling remains.

# Deliverables For Non-trivial UI Tasks

- Add a brief UI audit note for the touched area:
- Include inconsistencies found.
- Include what was standardized.
- Place token updates in one central location when needed.
- Update or add primitives rather than introducing one-off styles.
- Refactor touched screens/components to consume primitives.
- Include the done checklist in the PR description.

# Minimum Token Set

- Colors: `--bg`, `--surface`, `--surface-elevated`, `--text`, `--text-muted`, `--text-placeholder`, `--border`, `--divider`, `--accent`, `--accent-foreground`, `--danger`, `--warning`, `--success`, `--focus-ring`, `--hover-overlay`, `--active-overlay`
- Radii: `sm`, `md`, `lg`, `xl`
- Shadows: `none`, `sm`, `md`
- Typography: `sans`, `mono`; sizes `xs`, `sm`, `base`, `lg`, `xl`, `2xl`
- Spacing: 4px-based scale

# Recommended Paths (adapt if repo differs)

- `src/styles/tokens.css`
- `src/lib/cn.ts`
- `src/components/ui/*`
- `src/components/shell/AppShell.tsx`
- `src/components/shell/Sidebar.tsx`
- `src/components/shell/CommandPalette.tsx`

# Autofix Heuristics

- Replace raw styled `<button>` with `Button`/`IconButton`.
- Migrate inline style colors/spacing into tokens + shared utilities.
- Extract repeated class strings into primitive variants.
- Align random borders/shadows to tokenized border/shadow levels.
- For dense tables, provide table primitive density variants (`comfortable`, `compact`).

# Non-goals

- Do not copy proprietary Notion code/assets.
- Do not add heavy animation dependencies without strong justification.
- Do not add new dependencies without clear need.

# Decision Rule Under Uncertainty

Prefer fewer accents and more whitespace, subtle borders, and clear typography.

# Definition of Done (PR checklist)

- [ ] No hardcoded colors or arbitrary spacing/radius outside tokens/theme.
- [ ] Uses primitives for all controls (no bespoke raw control styling).
- [ ] Consistent typography and spacing rhythm in changed area.
- [ ] Hover/active/focus/disabled/loading states implemented.
- [ ] Works in light and dark mode.
- [ ] Keyboard navigable and ARIA-correct for overlays/menus/dialogs.
- [ ] Empty/error states look intentional.
