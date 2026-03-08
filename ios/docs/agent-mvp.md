# Agent MVP

## Scope

- `BillHelperFeatures/Sources/AgentFeature.swift`
- `BillHelperFeatures/Sources/PlaceholderFeatures.swift`
- `BillHelperAPITests/AgentFeatureViewModelTests.swift`

## Threads

- the agent tab shows a mobile-first thread list with loading, empty, error, and pull-to-refresh states
- creating a thread immediately pushes into thread detail so the next user action stays focused on messaging

## Thread Detail

- thread detail renders assistant and user messages, current run state, recent live stream text/reasoning, and pending review cards
- assistant-authored message bubbles render `contentMarkdown` with Apple markdown formatting support; user/system messages remain plain text
- the composer supports text send plus invoice/receipt attachments from Photos or the file importer
- the composer locks while imports/uploads are in flight and surfaces attachment/read/send errors inline

## Review Actions

- pending proposal cards expose approve and reject actions in-place
- review state updates the thread detail immediately and refreshes the parent list summary

## Notes

- the live agent surface is mounted through `AgentPlaceholderView` to avoid shared navigation churn with the parallel dashboard/entries work
- no local backend port was required for this work item; verification used `xcodebuild test` plus injected view-model tests