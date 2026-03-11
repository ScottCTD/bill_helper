import SwiftUI

struct PendingAgentComposerMessage: Identifiable, Equatable {
    let id = UUID()
    let threadID: String
    let content: String
    let attachments: [ComposerAttachment]
    let createdAt: String
}

struct AgentPresentedToolCall: Identifiable, Equatable {
    let id: String
    let toolCallID: String
    let createdAt: String
    let toolCall: AgentToolCall?
    let statusText: String
}

struct AgentPresentedRun: Identifiable, Equatable {
    let run: AgentRun
    let reasoningEvents: [AgentRunEvent]
    let toolCalls: [AgentPresentedToolCall]
    let streamingReasoningText: String
    let streamingAssistantText: String
    let showsStreamingPlaceholder: Bool

    var id: String { run.id }

    var hasActivityContent: Bool {
        !reasoningEvents.isEmpty
            || !toolCalls.isEmpty
            || !streamingReasoningText.isEmpty
            || !streamingAssistantText.isEmpty
            || showsStreamingPlaceholder
            || (run.errorText?.isEmpty == false)
    }
}

struct AgentThreadConversationState {
    let runsByAssistantMessageID: [String: [AgentPresentedRun]]
    let pendingRunsByUserMessageID: [String: [AgentPresentedRun]]
    let detachedRuns: [AgentPresentedRun]
    let pendingUserMessage: PendingAgentComposerMessage?
    let pendingUserRun: AgentPresentedRun?
    let showsPendingAssistantPlaceholder: Bool

    init(
        messages: [AgentMessage],
        runs: [AgentRun],
        activeRun: AgentRun?,
        pendingUserMessage: PendingAgentComposerMessage?,
        liveReasoning: String,
        liveText: String,
        liveEvents: [AgentRunEvent],
        hydratedToolCallsByID: [String: AgentToolCall],
        isSending: Bool
    ) {
        let messageIDs = Set(messages.map(\.id))
        let activeRunID = activeRun?.id
        let presentedRuns = runs.map { run in
            Self.presentedRun(
                from: run,
                isActive: run.id == activeRunID,
                liveReasoning: liveReasoning,
                liveText: liveText,
                liveEvents: run.id == activeRunID ? liveEvents : [],
                hydratedToolCallsByID: hydratedToolCallsByID
            )
        }

        var byAssistantMessageID: [String: [AgentPresentedRun]] = [:]
        var byUserMessageID: [String: [AgentPresentedRun]] = [:]
        var detached: [AgentPresentedRun] = []

        for run in presentedRuns {
            if let assistantMessageID = run.run.assistantMessageId {
                byAssistantMessageID[assistantMessageID, default: []].append(run)
            } else if messageIDs.contains(run.run.userMessageId) {
                byUserMessageID[run.run.userMessageId, default: []].append(run)
            } else {
                detached.append(run)
            }
        }

        let pendingRun = pendingUserMessage.flatMap { pending in
            detached.first { $0.run.userMessageId == activeRun?.userMessageId || $0.run.threadId == pending.threadID }
        }

        runsByAssistantMessageID = byAssistantMessageID.mapValues { $0.sorted(by: { $0.run.createdAt < $1.run.createdAt }) }
        pendingRunsByUserMessageID = byUserMessageID.mapValues { $0.sorted(by: { $0.run.createdAt < $1.run.createdAt }) }
        detachedRuns = detached.sorted(by: { $0.run.createdAt < $1.run.createdAt })
        self.pendingUserMessage = pendingUserMessage
        pendingUserRun = pendingRun
        showsPendingAssistantPlaceholder = pendingUserMessage != nil && pendingRun == nil && isSending
    }

    private static func presentedRun(
        from run: AgentRun,
        isActive: Bool,
        liveReasoning: String,
        liveText: String,
        liveEvents: [AgentRunEvent],
        hydratedToolCallsByID: [String: AgentToolCall]
    ) -> AgentPresentedRun {
        let mergedEvents = mergeRunEvents(run.events, liveEvents)
        let reasoningEvents = mergedEvents.filter { $0.eventType == .reasoningUpdate }
        let toolCalls = resolveToolCalls(run.toolCalls, events: mergedEvents, hydratedToolCallsByID: hydratedToolCallsByID)
        let streamingReasoningText = isActive && run.assistantMessageId == nil ? liveReasoning : ""
        let streamingAssistantText = isActive && run.assistantMessageId == nil ? liveText : ""
        let showsStreamingPlaceholder = isActive
            && run.assistantMessageId == nil
            && reasoningEvents.isEmpty
            && toolCalls.isEmpty
            && streamingReasoningText.isEmpty
            && streamingAssistantText.isEmpty

        return AgentPresentedRun(
            run: run,
            reasoningEvents: reasoningEvents,
            toolCalls: toolCalls,
            streamingReasoningText: streamingReasoningText,
            streamingAssistantText: streamingAssistantText,
            showsStreamingPlaceholder: showsStreamingPlaceholder
        )
    }

    private static func mergeRunEvents(_ persisted: [AgentRunEvent], _ live: [AgentRunEvent]) -> [AgentRunEvent] {
        let merged = (persisted + live)
            .reduce(into: [String: AgentRunEvent]()) { partial, event in
                partial[event.id] = event
            }
            .values
            .sorted {
                if $0.sequenceIndex == $1.sequenceIndex {
                    return $0.createdAt < $1.createdAt
                }
                return $0.sequenceIndex < $1.sequenceIndex
            }
        return merged
    }

    private static func resolveToolCalls(
        _ toolCalls: [AgentToolCall],
        events: [AgentRunEvent],
        hydratedToolCallsByID: [String: AgentToolCall]
    ) -> [AgentPresentedToolCall] {
        let sortedToolCalls = toolCalls.sorted(by: { $0.createdAt < $1.createdAt })
        var seenToolCallIDs = Set<String>()
        var presented = sortedToolCalls.map { toolCall -> AgentPresentedToolCall in
            let resolved = hydratedToolCallsByID[toolCall.id] ?? toolCall
            seenToolCallIDs.insert(toolCall.id)
            return AgentPresentedToolCall(
                id: toolCall.id,
                toolCallID: toolCall.id,
                createdAt: resolved.createdAt,
                toolCall: resolved,
                statusText: agentToolCallStatusText(resolved.status)
            )
        }

        for event in events where event.toolCallId != nil {
            guard let toolCallID = event.toolCallId, !seenToolCallIDs.contains(toolCallID) else { continue }
            presented.append(
                AgentPresentedToolCall(
                    id: toolCallID,
                    toolCallID: toolCallID,
                    createdAt: event.createdAt,
                    toolCall: hydratedToolCallsByID[toolCallID],
                    statusText: readableEventType(event.eventType)
                )
            )
            seenToolCallIDs.insert(toolCallID)
        }

        return presented.sorted(by: { $0.createdAt < $1.createdAt })
    }
}

struct AgentPendingUserMessageCard: View {
    let message: PendingAgentComposerMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            AgentBubbleHeader(role: "You", symbol: "person.fill", timestamp: agentRelativeTimestamp(message.createdAt))
            if message.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                Text("(attachment-only message)")
                    .foregroundStyle(.secondary)
            } else {
                Text(message.content)
            }

            if !message.attachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(message.attachments) { attachment in
                            Label(attachment.filename, systemImage: attachment.mimeType == "application/pdf" ? "doc.richtext" : "photo")
                                .font(.caption.weight(.medium))
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(Color.secondary.opacity(0.12), in: Capsule())
                        }
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(agentBubbleBackgroundColor(for: .user), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

struct AgentPendingAssistantBubble: View {
    let run: AgentPresentedRun?
    let timestamp: String
    let hydratingToolCallIDs: Set<String>
    let onHydrateToolCall: (String) -> Void
    let onOpenToolCall: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            AgentBubbleHeader(role: "Agent", symbol: "ellipsis.bubble.fill", timestamp: agentRelativeTimestamp(timestamp))
            if let run {
                AgentRunActivityBlock(
                    presentedRun: run,
                    hydratingToolCallIDs: hydratingToolCallIDs,
                    onHydrateToolCall: onHydrateToolCall,
                    onOpenToolCall: onOpenToolCall
                )
            } else {
                Label("Waiting for the assistant to respond…", systemImage: "ellipsis.bubble")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(agentBubbleBackgroundColor(for: .assistant), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }
}

struct AgentRunActivityBlock: View {
    let presentedRun: AgentPresentedRun
    let hydratingToolCallIDs: Set<String>
    let onHydrateToolCall: (String) -> Void
    let onOpenToolCall: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                AgentPill(text: runStatusText(presentedRun.run.status), tint: runStatusTint(presentedRun.run.status))
                if let totalCostUsd = presentedRun.run.totalCostUsd {
                    Text(totalCostUsd.formatted(.currency(code: "USD")))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(agentRelativeTimestamp(presentedRun.run.createdAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let errorText = presentedRun.run.errorText, !errorText.isEmpty {
                Label(errorText, systemImage: "exclamationmark.triangle.fill")
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            if !presentedRun.toolCalls.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Tool calls")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    ForEach(presentedRun.toolCalls) { toolCall in
                        AgentToolCallDisclosure(
                            toolCall: toolCall,
                            isHydrating: hydratingToolCallIDs.contains(toolCall.toolCallID),
                            onHydrate: onHydrateToolCall,
                            onOpenToolCall: onOpenToolCall
                        )
                    }
                }
            }

            if !presentedRun.reasoningEvents.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Reasoning")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    ForEach(presentedRun.reasoningEvents, id: \.id) { event in
                        AgentReasoningDisclosure(
                            id: event.id,
                            title: reasoningSourceLabel(event.source),
                            markdown: event.message ?? readableEventType(event.eventType),
                            isLive: false,
                            tint: .secondary
                        )
                    }
                }
            }

            if !presentedRun.streamingReasoningText.isEmpty {
                AgentReasoningDisclosure(
                    id: "\(presentedRun.run.id)-stream-reasoning",
                    title: "Live reasoning",
                    markdown: presentedRun.streamingReasoningText,
                    isLive: true,
                    tint: .indigo
                )
            }

            if !presentedRun.streamingAssistantText.isEmpty || presentedRun.showsStreamingPlaceholder {
                AgentReasoningDisclosure(
                    id: "\(presentedRun.run.id)-stream-assistant",
                    title: "Assistant reply",
                    markdown: presentedRun.streamingAssistantText.isEmpty ? "▍" : presentedRun.streamingAssistantText,
                    isLive: true,
                    tint: .indigo
                )
            }

            if !presentedRun.run.changeItems.isEmpty {
                AgentRunChangeSummaryView(changeItems: presentedRun.run.changeItems)
            }
        }
    }
}

private struct AgentBubbleHeader: View {
    let role: String
    let symbol: String
    let timestamp: String

    var body: some View {
        HStack {
            Label(role, systemImage: symbol)
                .font(.subheadline.weight(.semibold))
            Spacer()
            Text(timestamp)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

private struct AgentReasoningDisclosure: View {
    let id: String
    let title: String
    let markdown: String
    let isLive: Bool
    let tint: Color

    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            AgentMarkdownText(
                rendered: AssistantMessageMarkdownRenderer.renderedContent(forMarkdown: markdown, messageID: id),
                tint: isLive ? tint : .indigo
            )
            .font(.footnote)
            .padding(.top, 4)
        } label: {
            HStack(spacing: 8) {
                AgentPill(text: isLive ? "Live" : "Saved", tint: isLive ? tint : .secondary)
                Text(title)
                    .font(.footnote.weight(.semibold))
                Spacer()
                Text(reasoningPreview(markdown))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(12)
        .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

private struct AgentToolCallDisclosure: View {
    let toolCall: AgentPresentedToolCall
    let isHydrating: Bool
    let onHydrate: (String) -> Void
    let onOpenToolCall: (String) -> Void

    @State private var isExpanded = false

    var body: some View {
        DisclosureGroup(isExpanded: $isExpanded) {
            VStack(alignment: .leading, spacing: 10) {
                if let toolCall = toolCall.toolCall, toolCall.hasFullPayload {
                    if let inputJson = toolCall.inputJson {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Arguments")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.secondary)
                            Text(prettyJSONPreview(inputJson))
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                        }
                    }

                    if let outputText = toolCall.outputText, !outputText.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Model-visible result")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.secondary)
                            AgentMarkdownText(rendered: AssistantMessageMarkdownRenderer.renderedContent(forMarkdown: outputText, messageID: toolCall.id))
                                .font(.caption)
                        }
                    }

                    Button("Open full tool detail") {
                        onOpenToolCall(toolCall.id)
                    }
                    .buttonStyle(.bordered)
                } else if isHydrating {
                    Label("Loading tool details…", systemImage: "arrow.triangle.2.circlepath")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Expand again if the tool detail stays unavailable, or open the detail sheet after hydration finishes.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.top, 6)
        } label: {
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(toolCall.toolCall?.toolName ?? "Tool call")
                        .font(.footnote.weight(.semibold))
                    Text(toolCall.statusText)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(agentRelativeTimestamp(toolCall.createdAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .onChange(of: isExpanded) { _, expanded in
            guard expanded else { return }
            if toolCall.toolCall?.hasFullPayload != true {
                onHydrate(toolCall.toolCallID)
            }
        }
        .padding(12)
        .background(Color.indigo.opacity(0.06), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

private struct AgentRunChangeSummaryView: View {
    let changeItems: [AgentChangeItem]

    var body: some View {
        let grouped = Dictionary(grouping: changeItems, by: summarizeChangeFamily)
        let orderedFamilies = grouped.keys.sorted()
        let pendingCount = changeItems.filter { $0.status == .pendingReview }.count

        VStack(alignment: .leading, spacing: 10) {
            Text(pendingCount > 0 ? "\(pendingCount) proposal\(pendingCount == 1 ? "" : "s") pending review" : "Reviewed changes in this run")
                .font(.footnote.weight(.semibold))
            HStack(spacing: 8) {
                ForEach(orderedFamilies, id: \.self) { family in
                    AgentPill(text: "\(family) x\(grouped[family]?.count ?? 0)", tint: .orange)
                }
            }
        }
        .padding(12)
        .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func summarizeChangeFamily(_ change: AgentChangeItem) -> String {
        switch change.changeType {
        case .createEntry, .updateEntry, .deleteEntry:
            return "Entry"
        case .createAccount, .updateAccount, .deleteAccount:
            return "Account"
        case .createGroup, .updateGroup, .deleteGroup, .createGroupMember, .deleteGroupMember:
            return "Group"
        case .createTag, .updateTag, .deleteTag:
            return "Tag"
        case .createEntity, .updateEntity, .deleteEntity:
            return "Entity"
        }
    }
}

func agentBubbleBackgroundColor(for role: AgentMessageRole) -> Color {
    switch role {
    case .assistant: Color.indigo.opacity(0.08)
    case .system: Color.secondary.opacity(0.10)
    case .user: Color.green.opacity(0.10)
    }
}

func agentToolCallStatusText(_ status: AgentToolCallStatus) -> String {
    switch status {
    case .queued:
        return "Queued"
    case .running:
        return "Running"
    case .ok:
        return "Completed"
    case .error:
        return "Failed"
    case .cancelled:
        return "Cancelled"
    }
}

func reasoningSourceLabel(_ source: AgentRunEventSource?) -> String {
    switch source {
    case .assistantContent:
        return "Assistant update"
    case .modelReasoning:
        return "Model reasoning"
    case .toolCall:
        return "Tool note"
    case nil:
        return "Reasoning"
    }
}

func reasoningPreview(_ text: String) -> String {
    let preview = text
        .replacingOccurrences(of: "\n", with: " ")
        .trimmingCharacters(in: .whitespacesAndNewlines)
    guard !preview.isEmpty else { return "Open details" }
    return String(preview.prefix(72))
}

func agentRelativeTimestamp(_ value: String) -> String {
    relativeTimestamp(value)
}
