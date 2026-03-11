# iOS Documentation

This file is the iOS index. Use it to find the native-client docs under `../ios/docs/`.

## iOS Doc Map

- `../ios/README.md`: local package overview, run loop, and verification commands.
- `../ios/docs/README.md`: topic map for iOS-specific behavior docs.
- `../ios/docs/app-shell-and-session.md`: onboarding, saved connection state, tab shell, and deep links.
- `../ios/docs/dashboard-entries.md`: dashboard charts, entries filters, detail flows, and editor behavior.
- `../ios/docs/manage-and-settings.md`: management workspaces, settings editor, diagnostics, and admin gating.
- `../ios/docs/agent.md`: agent threads, run state, attachments, tool calls, and review flows.

## Stable Boundaries

- Native app-shell and resource wiring live under `ios/BillHelperApp/`.
- Shared transport, models, and session infrastructure live under `ios/BillHelperCore/`.
- Screen behavior and SwiftUI feature composition live under `ios/BillHelperFeatures/`.
- iOS-specific shipped behavior belongs in `ios/docs/*.md`, while cross-repo architecture stays under `docs/`.

## Related Docs

- `docs/development.md`
- `docs/api.md`
- `docs/repository-structure.md`
