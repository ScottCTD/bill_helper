# iOS Documentation

This file is the iOS index. Use it to find the native-client docs under `../ios/docs/`.

## iOS Doc Map

- `../ios/README.md`: local package overview, run loop, and verification commands.
- `../ios/docs/README.md`: topic map for iOS-specific behavior docs.
- `../ios/docs/dashboard_and_entries_mvp.md`: dashboard and entries MVP behavior.
- `../ios/docs/agent_mvp.md`: agent thread, upload, run-state, and review behavior.

## Stable Boundaries

- Native app-shell and resource wiring live under `ios/BillHelperApp/`.
- Shared transport, models, and session infrastructure live under `ios/BillHelperCore/`.
- Screen behavior and SwiftUI feature composition live under `ios/BillHelperFeatures/`.
- iOS-specific shipped behavior belongs in `ios/docs/*.md`, while cross-repo architecture stays under `docs/`.

## Related Docs

- `docs/development.md`
- `docs/api.md`
- `docs/repository_structure.md`
