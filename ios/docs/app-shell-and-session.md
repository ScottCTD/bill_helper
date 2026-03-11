# App Shell And Session

## Scope

This document describes the shipped iPhone app shell, the principal-based onboarding flow, and the deep-link routes handled by the native client.

## Onboarding

- the app starts in onboarding when there is no saved session in Keychain
- onboarding collects a backend base URL and principal name
- `Test connection` calls `GET /settings` with a principal-backed session before the app saves anything
- on success, the app stores the base URL in app preferences and the principal session in Keychain, then swaps into the main tab shell without relaunch
- `Settings` lets the user change the base URL or principal and re-run the same connection test

## Tab Shell

- the app is iPhone-only and uses one `NavigationStack` per tab
- the five tabs are `Dashboard`, `Entries`, `Agent`, `Manage`, and `Settings`
- the environment badge in the navigation bar still comes from `AppConfiguration`
- the live `APIClient` and `AgentRunTransport` are rebuilt from the currently saved base URL and session

## Session Behavior

- Keychain stores the current session credential
- app preferences store the last successful backend base URL
- signing out clears the saved session and returns the app to onboarding
- the saved base URL is intentionally kept so reconnecting to the same backend does not require retyping it

## Deep Links

The app registers the `billhelper://` URL scheme and routes these links into the relevant tab stack:

- `billhelper://dashboard?month=2026-03`
- `billhelper://entries/<entry-id>`
- `billhelper://accounts/<account-id>`
- `billhelper://groups/<group-id>`
- `billhelper://agent/threads/<thread-id>`
- `billhelper://settings`

## Files

- `ios/BillHelperApp/Sources/AppState.swift`
- `ios/BillHelperApp/Sources/OnboardingView.swift`
- `ios/BillHelperApp/Sources/AppShellView.swift`
- `ios/BillHelperCore/Sources/SessionInfrastructure.swift`
