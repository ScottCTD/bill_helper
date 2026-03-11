import XCTest
@testable import BillHelperApp

@MainActor
final class AgentFeatureViewModelTests: XCTestCase {
    func testAssistantMarkdownRendererFormatsAssistantMessages() async throws {
        let message = makeMessage(
            id: "message-1",
            role: .assistant,
            content: "**Bold** [link](https://example.com)"
        )

        let rendered = try XCTUnwrap(AssistantMessageMarkdownRenderer.renderedContent(for: message))

        XCTAssertEqual(String(rendered.characters), "Bold link")
        XCTAssertTrue(rendered.runs.contains { $0.inlinePresentationIntent?.contains(.stronglyEmphasized) == true })
        XCTAssertTrue(rendered.runs.contains { $0.link == URL(string: "https://example.com")! })
    }

    func testAssistantMarkdownRendererLeavesUserMessagesAsPlainText() async {
        let message = makeMessage(id: "message-2", role: .user, content: "**Bold**")

        XCTAssertNil(AssistantMessageMarkdownRenderer.renderedContent(for: message))
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
        XCTAssertNil(viewModel.actionError)
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
        changeItems: [AgentChangeItem]
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
            events: [],
            toolCalls: [],
            changeItems: changeItems
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
