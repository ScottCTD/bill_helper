# Agent

## Thread Workspace

- the agent tab shows a thread list and detail flow backed by the native agent transport plus the extended agent route family
- thread rows support create, rename, and delete
- initial agent-thread deep links are resolved after the thread list loads, so a cold-start open still pushes into the requested thread once summaries arrive
- selecting a thread loads messages, runs, review items, and configured model metadata
- non-admin principals see an explicit access-required state with a shortcut into `billhelper://settings`

## Detail View

- assistant markdown is rendered through the shared markdown renderer, keeps list/code/blockquote spacing stable even when streamed text arrives with weak formatting, normalizes display text before rendering, strips unsupported standalone decorative emoji that currently render as missing glyphs on iOS, and stays visually aligned with the assistant bubble instead of inheriting a selectable white card
- the composer supports text plus Photos/file-import attachments
- attachment validation uses runtime settings for max image size and image count
- thread detail shows:
  - a message-anchored assistant activity bubble directly below the triggering user message
  - live reasoning and streamed assistant text inside that assistant bubble instead of a detached status card above the thread
  - run events and change summaries inline with the assistant timeline
  - hydrated tool-call drill-down sheets
  - attachment preview/download sheets
  - pending review cards
  - rejected or failed review cards with reopen actions
  - automatic stick-to-bottom behavior while a run is active plus a manual jump-to-latest affordance when the user has scrolled away

## Review And Mutations

- approve and reject mutate the local run state immediately and then refresh the parent summary
- reopen moves rejected or apply-failed items back into pending review when the backend accepts the request
- thread rename and delete are local-first and restore prior state if the mutation fails
- hydrated tool calls are cached locally once opened so repeat inspection does not re-fetch unchanged payloads

## Files

- `ios/BillHelperFeatures/Sources/AgentFeature.swift`
- `ios/BillHelperFeatures/Sources/AgentMarkdownSupport.swift`
- `ios/BillHelperFeatures/Sources/AgentTimelineSupport.swift`
- `ios/BillHelperFeatures/Sources/AgentSupportViews.swift`
- `ios/BillHelperCore/Sources/APIClient.swift`
- `ios/BillHelperCore/Sources/APIClient+AgentExtensions.swift`
- `ios/BillHelperCore/Sources/AgentModels.swift`
- `ios/BillHelperCore/Sources/AgentRunTransport.swift`
