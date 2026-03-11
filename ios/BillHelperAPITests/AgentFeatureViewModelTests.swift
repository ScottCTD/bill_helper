import XCTest
@testable import BillHelperApp

@MainActor
final class AgentFeatureViewModelTests: XCTestCase {
    func testAssistantMarkdownRendererFormatsAssistantMessages() async throws {
        let message = makeMessage(
            id: "message-1",
            role: .assistant,
            content: "Hello\n- item one\n- item two\nAfter list"
        )

        let rendered = try XCTUnwrap(AssistantMessageMarkdownRenderer.renderedContent(for: message))

        XCTAssertEqual(rendered.markdown, "Hello\n\n- item one\n- item two\n\nAfter list")
        XCTAssertEqual(rendered.fallbackText, "Hello\n- item one\n- item two\nAfter list")
    }

    func testAssistantMarkdownRendererLeavesUserMessagesAsPlainText() async {
        let message = makeMessage(id: "message-2", role: .user, content: "**Bold**")

        XCTAssertNil(AssistantMessageMarkdownRenderer.renderedContent(for: message))
    }

    func testAssistantMarkdownRendererFallsBackForUnsupportedControlCharacters() async {
        let rendered = AssistantMessageMarkdownRenderer.renderedContent(
            forMarkdown: "Bad\u{0000}markdown",
            messageID: "message-bad"
        )

        XCTAssertNil(rendered.markdown)
        XCTAssertEqual(rendered.fallbackText, "Bad\u{0000}markdown")
    }

    func testListViewModelLoadsThreadsAndCreatesNewThread() async {
        let createdThread = makeThread(id: "thread-2", title: "Receipt follow-up")
        let client = AgentFeatureClient(
            listThreads: {
                [
                    AgentThreadSummary(
                        id: "thread-1",
                        title: "March bills",
                        createdAt: "2026-03-08T00:00:00Z",
                        updatedAt: "2026-03-08T00:00:00Z",
                        lastMessagePreview: "Need help",
                        pendingChangeCount: 1,
                        hasRunningRun: false
                    )
                ]
            },
            createThread: { _ in createdThread },
            renameThread: { _, _ in fatalError("unused") },
            deleteThread: { _ in fatalError("unused") },
            loadThread: { _ in fatalError("unused") },
            loadToolCall: { _ in fatalError("unused") },
            loadAttachment: { _ in fatalError("unused") },
            startMessageRun: { _, _, _ in fatalError("unused") },
            approveChange: { _ in fatalError("unused") },
            rejectChange: { _ in fatalError("unused") },
            reopenChange: { _ in fatalError("unused") }
        )

        let viewModel = AgentThreadListViewModel(client: client)

        await viewModel.loadIfNeeded()
        let createdSummary = await viewModel.createThread()

        XCTAssertEqual(viewModel.threads.count, 2)
        XCTAssertEqual(viewModel.threads.first?.id, "thread-2")
        XCTAssertEqual(createdSummary?.title, "Receipt follow-up")
    }

    func testDetailViewModelSendMessageRefreshesThreadState() async {
        let initialThread = makeThreadSummary(id: "thread-1", title: "March receipts")
        let initialDetail = AgentThreadDetail(
            thread: makeThread(id: "thread-1", title: "March receipts"),
            messages: [],
            runs: [],
            configuredModelName: "gpt-5",
            currentContextTokens: 12
        )
        let completedRun = makeRun(
            id: "run-1",
            status: .completed,
            assistantMessageID: "message-2",
            changeItems: []
        )
        let finalDetail = AgentThreadDetail(
            thread: makeThread(id: "thread-1", title: "March receipts"),
            messages: [
                makeMessage(id: "message-1", role: .user, content: "Review this receipt"),
                makeMessage(id: "message-2", role: .assistant, content: "Looks like a meal expense.")
            ],
            runs: [completedRun],
            configuredModelName: "gpt-5",
            currentContextTokens: 18
        )

        var loadCount = 0
        let client = AgentFeatureClient(
            listThreads: { [] },
            createThread: { _ in fatalError("unused") },
            renameThread: { _, _ in fatalError("unused") },
            deleteThread: { _ in fatalError("unused") },
            loadThread: { _ in
                loadCount += 1
                return loadCount == 1 ? initialDetail : finalDetail
            },
            loadToolCall: { _ in fatalError("unused") },
            loadAttachment: { _ in fatalError("unused") },
            startMessageRun: { _, _, _ in
                AsyncThrowingStream { continuation in
                    continuation.yield(.snapshot(completedRun))
                    continuation.finish()
                }
            },
            approveChange: { _ in fatalError("unused") },
            rejectChange: { _ in fatalError("unused") },
            reopenChange: { _ in fatalError("unused") }
        )

        let viewModel = AgentThreadDetailViewModel(thread: initialThread, client: client, attachmentLimits: nil)
        await viewModel.loadIfNeeded()
        viewModel.composerText = "Review this receipt"

        await viewModel.sendMessage()

        XCTAssertEqual(viewModel.messages.count, 2)
        XCTAssertEqual(viewModel.latestRun?.status, .completed)
        XCTAssertEqual(viewModel.composerText, "")
        XCTAssertNil(viewModel.pendingUserMessage)
        XCTAssertNil(viewModel.actionError)
    }

    func testConversationStatePlacesAssistantRunBelowPersistedUserMessage() async {
        let userMessage = makeMessage(id: "message-1", role: .user, content: "Hello")
        let runningRun = makeRun(
            id: "run-1",
            status: .running,
            assistantMessageID: nil,
            changeItems: []
        )

        let state = AgentThreadConversationState(
            messages: [userMessage],
            runs: [runningRun],
            activeRun: runningRun,
            pendingUserMessage: nil,
            liveReasoning: "Thinking about the receipt",
            liveText: "",
            liveEvents: [],
            hydratedToolCallsByID: [:],
            isSending: true
        )

        XCTAssertEqual(state.pendingRunsByUserMessageID["message-1"]?.first?.run.id, "run-1")
        XCTAssertNil(state.pendingUserMessage)
    }

    func testConversationStateAttachesActiveRunToPendingUserMessageBeforePersistence() async {
        let pendingUserMessage = PendingAgentComposerMessage(
            threadID: "thread-1",
            content: "Hello",
            attachments: [],
            createdAt: "2026-03-08T00:00:00Z"
        )
        let runningRun = makeRun(
            id: "run-1",
            status: .running,
            assistantMessageID: nil,
            changeItems: []
        )

        let state = AgentThreadConversationState(
            messages: [],
            runs: [runningRun],
            activeRun: runningRun,
            pendingUserMessage: pendingUserMessage,
            liveReasoning: "Thinking…",
            liveText: "",
            liveEvents: [],
            hydratedToolCallsByID: [:],
            isSending: true
        )

        XCTAssertEqual(state.pendingUserRun?.run.id, "run-1")
        XCTAssertFalse(state.showsPendingAssistantPlaceholder)
    }

    func testDetailViewModelApproveRemovesPendingReviewItem() async {
        let pendingItem = makeChangeItem(id: "item-1", status: .pendingReview)
        let initialThread = makeThreadSummary(id: "thread-1", title: "Review")
        let client = AgentFeatureClient(
            listThreads: { [] },
            createThread: { _ in fatalError("unused") },
            renameThread: { _, _ in fatalError("unused") },
            deleteThread: { _ in fatalError("unused") },
            loadThread: { _ in
                AgentThreadDetail(
                    thread: self.makeThread(id: "thread-1", title: "Review"),
                    messages: [],
                    runs: [self.makeRun(id: "run-1", status: .completed, assistantMessageID: nil, changeItems: [pendingItem])],
                    configuredModelName: "gpt-5",
                    currentContextTokens: nil
                )
            },
            loadToolCall: { _ in fatalError("unused") },
            loadAttachment: { _ in fatalError("unused") },
            startMessageRun: { _, _, _ in fatalError("unused") },
            approveChange: { _ in self.makeChangeItem(id: "item-1", status: .approved) },
            rejectChange: { _ in fatalError("unused") },
            reopenChange: { _ in fatalError("unused") }
        )

        let viewModel = AgentThreadDetailViewModel(thread: initialThread, client: client, attachmentLimits: nil)
        await viewModel.loadIfNeeded()
        XCTAssertEqual(viewModel.pendingReviewItems.count, 1)

        await viewModel.approve(itemID: "item-1")

        XCTAssertEqual(viewModel.pendingReviewItems.count, 0)
        XCTAssertNil(viewModel.actionError)
    }

    func testListViewModelRenameThreadUpdatesTitle() async {
        let client = AgentFeatureClient(
            listThreads: {
                [self.makeThreadSummary(id: "thread-1", title: "Old title")]
            },
            createThread: { _ in fatalError("unused") },
            renameThread: { id, title in
                self.makeThread(id: id, title: title)
            },
            deleteThread: { _ in fatalError("unused") },
            loadThread: { _ in fatalError("unused") },
            loadToolCall: { _ in fatalError("unused") },
            loadAttachment: { _ in fatalError("unused") },
            startMessageRun: { _, _, _ in fatalError("unused") },
            approveChange: { _ in fatalError("unused") },
            rejectChange: { _ in fatalError("unused") },
            reopenChange: { _ in fatalError("unused") }
        )

        let viewModel = AgentThreadListViewModel(client: client)
        await viewModel.loadIfNeeded()

        let renamed = await viewModel.renameThread(threadID: "thread-1", title: "New title")

        XCTAssertEqual(renamed?.title, "New title")
        XCTAssertEqual(viewModel.threads.first?.title, "New title")
        XCTAssertNil(viewModel.errorMessage)
    }

    func testDetailViewModelReopenMovesRejectedItemBackToPending() async {
        let rejectedItem = makeChangeItem(id: "item-1", status: .rejected)
        let initialThread = makeThreadSummary(id: "thread-1", title: "Review")
        let client = AgentFeatureClient(
            listThreads: { [] },
            createThread: { _ in fatalError("unused") },
            renameThread: { _, _ in fatalError("unused") },
            deleteThread: { _ in fatalError("unused") },
            loadThread: { _ in
                AgentThreadDetail(
                    thread: self.makeThread(id: "thread-1", title: "Review"),
                    messages: [],
                    runs: [self.makeRun(id: "run-1", status: .completed, assistantMessageID: nil, changeItems: [rejectedItem])],
                    configuredModelName: "gpt-5",
                    currentContextTokens: nil
                )
            },
            loadToolCall: { _ in fatalError("unused") },
            loadAttachment: { _ in fatalError("unused") },
            startMessageRun: { _, _, _ in fatalError("unused") },
            approveChange: { _ in fatalError("unused") },
            rejectChange: { _ in fatalError("unused") },
            reopenChange: { _ in self.makeChangeItem(id: "item-1", status: .pendingReview) }
        )

        let viewModel = AgentThreadDetailViewModel(thread: initialThread, client: client, attachmentLimits: nil)
        await viewModel.loadIfNeeded()
        XCTAssertEqual(viewModel.rejectedReviewItems.count, 1)

        await viewModel.reopen(itemID: "item-1")

        XCTAssertEqual(viewModel.rejectedReviewItems.count, 0)
        XCTAssertEqual(viewModel.pendingReviewItems.count, 1)
        XCTAssertNil(viewModel.actionError)
    }

    func testHydrateToolCallCachesLoadedPayload() async {
        let toolCall = makeToolCall(id: "tool-1", hasFullPayload: true)
        var loadCount = 0
        let client = AgentFeatureClient(
            listThreads: { [] },
            createThread: { _ in fatalError("unused") },
            renameThread: { _, _ in fatalError("unused") },
            deleteThread: { _ in fatalError("unused") },
            loadThread: { _ in
                AgentThreadDetail(
                    thread: self.makeThread(id: "thread-1", title: "Review"),
                    messages: [],
                    runs: [self.makeRun(id: "run-1", status: .running, assistantMessageID: nil, changeItems: [], toolCalls: [self.makeToolCall(id: "tool-1", hasFullPayload: false)])],
                    configuredModelName: "gpt-5",
                    currentContextTokens: nil
                )
            },
            loadToolCall: { _ in
                loadCount += 1
                return toolCall
            },
            loadAttachment: { _ in fatalError("unused") },
            startMessageRun: { _, _, _ in fatalError("unused") },
            approveChange: { _ in fatalError("unused") },
            rejectChange: { _ in fatalError("unused") },
            reopenChange: { _ in fatalError("unused") }
        )

        let viewModel = AgentThreadDetailViewModel(thread: makeThreadSummary(id: "thread-1", title: "Review"), client: client, attachmentLimits: nil)
        await viewModel.loadIfNeeded()

        await viewModel.hydrateToolCallIfNeeded(id: "tool-1")
        await viewModel.hydrateToolCallIfNeeded(id: "tool-1")

        XCTAssertEqual(loadCount, 1)
        XCTAssertEqual(viewModel.hydratedToolCallsByID["tool-1"], toolCall)
    }

    func testRelativeTimestampParsesNaiveFractionalTimestamp() async {
        XCTAssertNotEqual(relativeTimestamp("2026-03-11T13:30:45.359741"), "2026-03-11T13:30:45.359741")
    }

    private func makeThreadSummary(id: String, title: String?) -> AgentThreadSummary {
        AgentThreadSummary(
            id: id,
            title: title,
            createdAt: "2026-03-08T00:00:00Z",
            updatedAt: "2026-03-08T00:00:00Z",
            lastMessagePreview: nil,
            pendingChangeCount: 0,
            hasRunningRun: false
        )
    }

    private func makeThread(id: String, title: String?) -> AgentThread {
        AgentThread(id: id, title: title, createdAt: "2026-03-08T00:00:00Z", updatedAt: "2026-03-08T00:00:00Z")
    }

    private func makeMessage(id: String, role: AgentMessageRole, content: String) -> AgentMessage {
        AgentMessage(
            id: id,
            threadId: "thread-1",
            role: role,
            contentMarkdown: content,
            createdAt: "2026-03-08T00:00:00Z",
            attachments: []
        )
    }

    private func makeRun(
        id: String,
        status: AgentRunStatus,
        assistantMessageID: String?,
        changeItems: [AgentChangeItem],
        toolCalls: [AgentToolCall] = [],
        events: [AgentRunEvent] = []
    ) -> AgentRun {
        AgentRun(
            id: id,
            threadId: "thread-1",
            userMessageId: "message-1",
            assistantMessageId: assistantMessageID,
            terminalAssistantReply: assistantMessageID == nil ? nil : "Done",
            status: status,
            modelName: "gpt-5",
            surface: "ios",
            replySurface: "ios",
            contextTokens: nil,
            inputTokens: nil,
            outputTokens: nil,
            cacheReadTokens: nil,
            cacheWriteTokens: nil,
            inputCostUsd: nil,
            outputCostUsd: nil,
            totalCostUsd: nil,
            errorText: nil,
            createdAt: "2026-03-08T00:00:00Z",
            completedAt: status.isTerminal ? "2026-03-08T00:00:10Z" : nil,
            events: events,
            toolCalls: toolCalls,
            changeItems: changeItems
        )
    }

    private func makeToolCall(id: String, hasFullPayload: Bool) -> AgentToolCall {
        AgentToolCall(
            id: id,
            runId: "run-1",
            llmToolCallId: "llm-\(id)",
            toolName: "rename_thread",
            inputJson: hasFullPayload ? ["title": .string("March receipts")] : nil,
            outputJson: hasFullPayload ? ["status": .string("ok")] : nil,
            outputText: hasFullPayload ? "OK" : nil,
            hasFullPayload: hasFullPayload,
            status: .ok,
            createdAt: "2026-03-08T00:00:00Z",
            startedAt: "2026-03-08T00:00:01Z",
            completedAt: "2026-03-08T00:00:02Z"
        )
    }

    private func makeChangeItem(id: String, status: AgentChangeStatus) -> AgentChangeItem {
        AgentChangeItem(
            id: id,
            runId: "run-1",
            changeType: .createEntry,
            payloadJson: [
                "name": .string("Receipt"),
                "date": .string("2026-03-08")
            ],
            rationaleText: "Looks like an expense.",
            status: status,
            reviewNote: nil,
            appliedResourceType: nil,
            appliedResourceId: nil,
            createdAt: "2026-03-08T00:00:00Z",
            updatedAt: "2026-03-08T00:00:00Z",
            reviewActions: []
        )
    }
}
