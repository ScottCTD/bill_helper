# Agent

## Thread Workspace

- the agent tab shows a thread list and detail flow backed by the native agent transport plus the extended agent route family
- thread rows support create, rename, and delete
- selecting a thread loads messages, runs, review items, and configured model metadata
- non-admin principals see an explicit access-required state with a shortcut into `billhelper://settings`

## Detail View

- assistant markdown is rendered from `contentMarkdown`
- the composer supports text plus Photos/file-import attachments
- attachment validation uses runtime settings for max image size and image count
- thread detail shows:
  - live reasoning and text blocks
  - run events
  - hydrated tool-call drill-down sheets
  - attachment preview/download sheets
  - pending review cards
  - rejected or failed review cards with reopen actions

## Review And Mutations

- approve and reject mutate the local run state immediately and then refresh the parent summary
- reopen moves rejected or apply-failed items back into pending review when the backend accepts the request
- thread rename and delete are local-first and restore prior state if the mutation fails

## Files

- `ios/BillHelperFeatures/Sources/AgentFeature.swift`
- `ios/BillHelperCore/Sources/APIClient.swift`
- `ios/BillHelperCore/Sources/APIClient+AgentExtensions.swift`
- `ios/BillHelperCore/Sources/AgentModels.swift`
- `ios/BillHelperCore/Sources/AgentRunTransport.swift`
