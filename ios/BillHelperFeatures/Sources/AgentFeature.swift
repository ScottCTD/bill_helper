import PhotosUI
import SwiftUI
import UniformTypeIdentifiers
import UIKit
import os

private let agentMessageMarkdownLogger = Logger(subsystem: "com.billhelper.ios", category: "AgentMessageMarkdown")
private let threadTitleMaxLength = 80
private let threadTitleMaxWords = 5

struct AgentAttachmentLimits: Equatable {
    let maxImageSizeBytes: Int
    let maxImagesPerMessage: Int
}

struct AgentFeatureClient {
    var listThreads: () async throws -> [AgentThreadSummary]
    var createThread: (_ title: String?) async throws -> AgentThread
    var renameThread: (_ threadID: String, _ title: String) async throws -> AgentThread
    var deleteThread: (_ threadID: String) async throws -> Void
    var loadThread: (_ threadId: String) async throws -> AgentThreadDetail
    var loadToolCall: (_ toolCallID: String) async throws -> AgentToolCall
    var loadAttachment: (_ attachmentID: String) async throws -> AgentAttachmentResource
    var startMessageRun: (_ threadId: String, _ content: String, _ attachments: [AttachmentUpload]) -> AsyncThrowingStream<AgentRunUpdate, Error>
    var approveChange: (_ itemId: String) async throws -> AgentChangeItem
    var rejectChange: (_ itemId: String) async throws -> AgentChangeItem
    var reopenChange: (_ itemId: String) async throws -> AgentChangeItem

    static func live(apiClient: APIClient, transport: AgentRunTransport) -> AgentFeatureClient {
        AgentFeatureClient(
            listThreads: { try await apiClient.listAgentThreads() },
            createThread: { try await apiClient.createAgentThread(title: $0) },
            renameThread: { try await apiClient.renameAgentThread(id: $0, title: $1).asThread },
            deleteThread: { try await apiClient.deleteAgentThread(id: $0) },
            loadThread: { try await apiClient.agentThread(id: $0) },
            loadToolCall: { try await apiClient.agentToolCall(id: $0) },
            loadAttachment: { try await apiClient.agentAttachment(id: $0) },
            startMessageRun: { transport.startMessageRun(threadId: $0, content: $1, attachments: $2) },
            approveChange: { try await apiClient.approveChangeItem(id: $0) },
            rejectChange: { try await apiClient.rejectChangeItem(id: $0) },
            reopenChange: { try await apiClient.reopenChangeItem(id: $0) }
        )
    }
}

@MainActor
final class AgentAccessViewModel: ObservableObject {
    @Published private(set) var currentUser: User?
    @Published private(set) var attachmentLimits: AgentAttachmentLimits?
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?

    private let apiClient: APIClient
    private var hasLoaded = false

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    var isAdmin: Bool {
        currentUser?.isAdmin ?? false
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        await reload()
    }

    func reload() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let usersTask = apiClient.listUsers()
            async let settingsTask = apiClient.runtimeSettings()
            currentUser = try await usersTask.first(where: \.isCurrentUser)
            let settings = try await settingsTask
            attachmentLimits = AgentAttachmentLimits(
                maxImageSizeBytes: settings.agentMaxImageSizeBytes,
                maxImagesPerMessage: settings.agentMaxImagesPerMessage
            )
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
final class AgentThreadListViewModel: ObservableObject {
    @Published private(set) var threads: [AgentThreadSummary] = []
    @Published private(set) var isLoading = false
    @Published private(set) var isCreatingThread = false
    @Published private(set) var errorMessage: String?

    private let client: AgentFeatureClient
    private var hasLoaded = false

    init(client: AgentFeatureClient) {
        self.client = client
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        await reload()
    }

    func reload() async {
        isLoading = true
        defer { isLoading = false }

        do {
            threads = try await client.listThreads().sorted(by: { $0.updatedAt > $1.updatedAt })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func createThread() async -> AgentThreadSummary? {
        isCreatingThread = true
        defer { isCreatingThread = false }

        do {
            let thread = try await client.createThread(nil)
            let summary = AgentThreadSummary(
                id: thread.id,
                title: thread.title,
                createdAt: thread.createdAt,
                updatedAt: thread.updatedAt,
                lastMessagePreview: nil,
                pendingChangeCount: 0,
                hasRunningRun: false
            )
            threads = [summary] + threads.filter { $0.id != summary.id }
            errorMessage = nil
            return summary
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func renameThread(threadID: String, title: String) async -> AgentThreadSummary? {
        guard let index = threads.firstIndex(where: { $0.id == threadID }) else { return nil }
        let previous = threads[index]
        var optimistic = previous
        optimistic = AgentThreadSummary(
            id: previous.id,
            title: title,
            createdAt: previous.createdAt,
            updatedAt: previous.updatedAt,
            lastMessagePreview: previous.lastMessagePreview,
            pendingChangeCount: previous.pendingChangeCount,
            hasRunningRun: previous.hasRunningRun
        )
        threads[index] = optimistic

        do {
            let thread = try await client.renameThread(threadID, title)
            let updated = AgentThreadSummary(
                id: thread.id,
                title: thread.title,
                createdAt: thread.createdAt,
                updatedAt: thread.updatedAt,
                lastMessagePreview: previous.lastMessagePreview,
                pendingChangeCount: previous.pendingChangeCount,
                hasRunningRun: previous.hasRunningRun
            )
            threads[index] = updated
            errorMessage = nil
            return updated
        } catch {
            threads[index] = previous
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func deleteThread(threadID: String) async -> Bool {
        guard let index = threads.firstIndex(where: { $0.id == threadID }) else { return false }
        let removed = threads.remove(at: index)
        do {
            try await client.deleteThread(threadID)
            errorMessage = nil
            return true
        } catch {
            threads.insert(removed, at: index)
            errorMessage = error.localizedDescription
            return false
        }
    }
}

@MainActor
final class AgentThreadDetailViewModel: ObservableObject {
    @Published private(set) var threadTitle: String?
    @Published private(set) var messages: [AgentMessage] = []
    @Published private(set) var runs: [AgentRun] = []
    @Published private(set) var configuredModelName = ""
    @Published private(set) var currentContextTokens: Int?
    @Published private(set) var isLoading = false
    @Published private(set) var isImportingAttachment = false
    @Published private(set) var isSending = false
    @Published private(set) var activeReviewItemID: String?
    @Published private(set) var sendingAttachmentCount = 0
    @Published private(set) var liveReasoning = ""
    @Published private(set) var liveText = ""
    @Published private(set) var liveEvents: [AgentRunEvent] = []
    @Published private(set) var activeRun: AgentRun?
    @Published private(set) var errorMessage: String?
    @Published var actionError: String?
    @Published var composerText = ""
    @Published private(set) var attachments: [ComposerAttachment] = []
    @Published private(set) var isMutatingThread = false

    let threadID: String

    private let client: AgentFeatureClient
    private let attachmentLimits: AgentAttachmentLimits?
    private var hasLoaded = false

    init(thread: AgentThreadSummary, client: AgentFeatureClient, attachmentLimits: AgentAttachmentLimits?) {
        threadID = thread.id
        threadTitle = thread.title
        self.client = client
        self.attachmentLimits = attachmentLimits
    }

    var canSend: Bool {
        (!composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !attachments.isEmpty)
            && !isLoading
            && !isImportingAttachment
            && !isSending
    }

    var sortedRuns: [AgentRun] {
        var merged = runs
        if let activeRun {
            if let index = merged.firstIndex(where: { $0.id == activeRun.id }) {
                merged[index] = activeRun
            } else {
                merged.append(activeRun)
            }
        }
        return merged.sorted(by: { $0.createdAt < $1.createdAt })
    }

    var pendingReviewItems: [AgentReviewItem] {
        sortedRuns.flatMap { run in
            run.changeItems
                .filter { $0.status == .pendingReview }
                .map { AgentReviewItem(run: run, item: $0) }
        }
    }

    var rejectedReviewItems: [AgentReviewItem] {
        sortedRuns.flatMap { run in
            run.changeItems
                .filter { $0.status == .rejected || $0.status == .applyFailed }
                .map { AgentReviewItem(run: run, item: $0) }
        }
    }

    var latestRun: AgentRun? {
        sortedRuns.last
    }

    var reviewStatusText: String? {
        let count = pendingReviewItems.count
        guard count > 0 else { return nil }
        return "\(count) proposal\(count == 1 ? "" : "s") waiting for review"
    }

    var sendingStatusText: String? {
        if isImportingAttachment {
            return "Preparing attachment…"
        }
        if isSending && sendingAttachmentCount > 0 {
            return "Uploading \(sendingAttachmentCount) attachment\(sendingAttachmentCount == 1 ? "" : "s")…"
        }
        if isSending {
            return "Sending message…"
        }
        return nil
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        await reload()
    }

    func reload() async {
        isLoading = true
        defer { isLoading = false }
        await refreshThread(clearTransientError: false)
    }

    func importFileURLs(_ urls: [URL]) async {
        isImportingAttachment = true
        defer { isImportingAttachment = false }

        do {
            let imported = try urls.map(Self.loadAttachment(from:))
            try validateAttachmentBatch(imported)
            attachments.append(contentsOf: imported)
            actionError = nil
        } catch {
            actionError = error.localizedDescription
        }
    }

    func importPhotoItems(_ items: [PhotosPickerItem]) async {
        guard !items.isEmpty else { return }
        isImportingAttachment = true
        defer { isImportingAttachment = false }

        do {
            var imported: [ComposerAttachment] = []
            for item in items {
                guard let data = try await item.loadTransferable(type: Data.self) else {
                    throw AttachmentImportError.unreadableAsset
                }
                let contentType = item.supportedContentTypes.first(where: { $0.conforms(to: .image) }) ?? .jpeg
                let fileExtension = contentType.preferredFilenameExtension ?? "jpg"
                let mimeType = contentType.preferredMIMEType ?? "image/jpeg"
                let upload = try AttachmentUpload(
                    filename: "photo-\(UUID().uuidString.prefix(8)).\(fileExtension)",
                    mimeType: mimeType,
                    data: data
                )
                imported.append(ComposerAttachment(upload: upload))
            }
            try validateAttachmentBatch(imported)
            attachments.append(contentsOf: imported)
            actionError = nil
        } catch {
            actionError = error.localizedDescription
        }
    }

    func removeAttachment(id: UUID) {
        attachments.removeAll { $0.id == id }
    }

    func sendMessage() async {
        let trimmed = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        let draftText = trimmed
        let draftAttachments = attachments
        guard !draftText.isEmpty || !draftAttachments.isEmpty else { return }

        composerText = ""
        attachments = []
        isSending = true
        sendingAttachmentCount = draftAttachments.count
        actionError = nil
        liveReasoning = ""
        liveText = ""
        liveEvents = []
        activeRun = nil

        defer {
            isSending = false
            sendingAttachmentCount = 0
        }

        do {
            var didRefreshAfterStart = false
            for try await update in client.startMessageRun(threadID, draftText, draftAttachments.map(\.upload)) {
                if !didRefreshAfterStart {
                    didRefreshAfterStart = true
                    await refreshThread(clearTransientError: true)
                }
                consume(update)
                if let run = activeRun, run.assistantMessageId != nil || run.status.isTerminal {
                    await refreshThread(clearTransientError: true)
                }
            }
            await refreshThread(clearTransientError: true)
            activeRun = nil
            liveReasoning = ""
            liveText = ""
            liveEvents = []
        } catch {
            composerText = draftText
            attachments = draftAttachments
            actionError = error.localizedDescription
        }
    }

    func approve(itemID: String) async {
        await updateReview(itemID: itemID, operation: client.approveChange)
    }

    func reject(itemID: String) async {
        await updateReview(itemID: itemID, operation: client.rejectChange)
    }

    func reopen(itemID: String) async {
        await updateReview(itemID: itemID, operation: client.reopenChange)
    }

    func renameThread(title: String) async -> Bool {
        isMutatingThread = true
        defer { isMutatingThread = false }
        do {
            let thread = try await client.renameThread(threadID, title)
            threadTitle = thread.title
            actionError = nil
            return true
        } catch {
            actionError = error.localizedDescription
            return false
        }
    }

    func deleteThread() async -> Bool {
        isMutatingThread = true
        defer { isMutatingThread = false }
        do {
            try await client.deleteThread(threadID)
            actionError = nil
            return true
        } catch {
            actionError = error.localizedDescription
            return false
        }
    }

    func loadToolCall(id: String) async throws -> AgentToolCall {
        try await client.loadToolCall(id)
    }

    func loadAttachment(_ attachment: AgentMessageAttachment) async throws -> AgentLoadedAttachment {
        let resource = try await client.loadAttachment(attachment.id)
        return try AgentLoadedAttachment(resource: resource)
    }

    private func updateReview(
        itemID: String,
        operation: (String) async throws -> AgentChangeItem
    ) async {
        activeReviewItemID = itemID
        defer { activeReviewItemID = nil }

        do {
            let updated = try await operation(itemID)
            replaceChangeItem(updated)
            actionError = nil
        } catch {
            actionError = error.localizedDescription
        }
    }

    private func refreshThread(clearTransientError: Bool) async {
        do {
            let detail = try await client.loadThread(threadID)
            threadTitle = detail.thread.title
            messages = detail.messages.sorted(by: { $0.createdAt < $1.createdAt })
            runs = detail.runs.sorted(by: { $0.createdAt < $1.createdAt })
            configuredModelName = detail.configuredModelName
            currentContextTokens = detail.currentContextTokens
            errorMessage = nil
            hasLoaded = true
            if clearTransientError {
                actionError = nil
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func consume(_ update: AgentRunUpdate) {
        switch update {
        case .snapshot(let run):
            activeRun = run
            upsertRun(run)
        case .event(let event):
            switch event {
            case .reasoningDelta(_, let delta):
                liveReasoning += delta
            case .textDelta(_, let delta):
                liveText += delta
            case .runEvent(_, let event, _):
                if !liveEvents.contains(where: { $0.id == event.id }) {
                    liveEvents.append(event)
                }
            }
        }
    }

    private func upsertRun(_ run: AgentRun) {
        if let index = runs.firstIndex(where: { $0.id == run.id }) {
            runs[index] = run
        } else {
            runs.append(run)
            runs.sort(by: { $0.createdAt < $1.createdAt })
        }
    }

    private func replaceChangeItem(_ updated: AgentChangeItem) {
        guard let runIndex = runs.firstIndex(where: { $0.id == updated.runId }) else { return }
        guard let itemIndex = runs[runIndex].changeItems.firstIndex(where: { $0.id == updated.id }) else { return }

        var items = runs[runIndex].changeItems
        items[itemIndex] = updated

        let run = runs[runIndex]
        runs[runIndex] = AgentRun(
            id: run.id,
            threadId: run.threadId,
            userMessageId: run.userMessageId,
            assistantMessageId: run.assistantMessageId,
            terminalAssistantReply: run.terminalAssistantReply,
            status: run.status,
            modelName: run.modelName,
            surface: run.surface,
            replySurface: run.replySurface,
            contextTokens: run.contextTokens,
            inputTokens: run.inputTokens,
            outputTokens: run.outputTokens,
            cacheReadTokens: run.cacheReadTokens,
            cacheWriteTokens: run.cacheWriteTokens,
            inputCostUsd: run.inputCostUsd,
            outputCostUsd: run.outputCostUsd,
            totalCostUsd: run.totalCostUsd,
            errorText: run.errorText,
            createdAt: run.createdAt,
            completedAt: run.completedAt,
            events: run.events,
            toolCalls: run.toolCalls,
            changeItems: items
        )
    }

    private static func loadAttachment(from url: URL) throws -> ComposerAttachment {
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed {
                url.stopAccessingSecurityScopedResource()
            }
        }

        let values = try? url.resourceValues(forKeys: [.contentTypeKey, .nameKey])
        let filename = values?.name ?? url.lastPathComponent
        let mimeType = preferredMimeType(contentType: values?.contentType, fallbackURL: url)
        let upload = try AttachmentUpload(filename: filename.isEmpty ? "attachment" : filename, mimeType: mimeType, data: try Data(contentsOf: url))
        return ComposerAttachment(upload: upload)
    }

    private static func preferredMimeType(contentType: UTType?, fallbackURL: URL) -> String {
        if let preferred = contentType?.preferredMIMEType {
            return preferred
        }
        if contentType?.conforms(to: .pdf) == true || fallbackURL.pathExtension.lowercased() == "pdf" {
            return "application/pdf"
        }
        return "image/jpeg"
    }

    private func validateAttachmentBatch(_ incoming: [ComposerAttachment]) throws {
        guard let attachmentLimits else { return }
        let totalImageCount = (attachments + incoming).filter { $0.mimeType.hasPrefix("image/") }.count
        if totalImageCount > attachmentLimits.maxImagesPerMessage {
            throw AttachmentImportError.tooManyImages(limit: attachmentLimits.maxImagesPerMessage)
        }
        for attachment in incoming where attachment.mimeType.hasPrefix("image/") {
            if attachment.upload.data.count > attachmentLimits.maxImageSizeBytes {
                throw AttachmentImportError.imageTooLarge(limit: attachmentLimits.maxImageSizeBytes)
            }
        }
    }
}

struct AgentRootView: View {
    let configuration: AppConfiguration
    let client: AgentFeatureClient
    @Binding private var deepLink: AppDeepLink?

    @StateObject private var accessModel: AgentAccessViewModel
    @StateObject private var viewModel: AgentThreadListViewModel
    @State private var selectedThread: AgentThreadSummary?
    @State private var renameTarget: AgentThreadSummary?
    @State private var deleteTarget: AgentThreadSummary?
    @State private var pendingDeepLinkThreadID: String?

    init(configuration: AppConfiguration, client: AgentFeatureClient, deepLink: Binding<AppDeepLink?>, apiClient: APIClient? = nil) {
        self.configuration = configuration
        self.client = client
        _deepLink = deepLink
        _accessModel = StateObject(wrappedValue: AgentAccessViewModel(apiClient: apiClient ?? APIClient(baseURL: configuration.apiBaseURL)))
        _viewModel = StateObject(wrappedValue: AgentThreadListViewModel(client: client))
    }

    var body: some View {
        Group {
            if accessModel.isLoading && accessModel.currentUser == nil {
                ProgressView("Loading agent access…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(.systemGroupedBackground))
            } else if accessModel.isAdmin == false {
                AgentAccessRequiredView(principalName: accessModel.currentUser?.name)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(.systemGroupedBackground))
            } else if viewModel.isLoading && viewModel.threads.isEmpty {
                ProgressView("Loading threads…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(.systemGroupedBackground))
            } else if viewModel.threads.isEmpty {
                ContentUnavailableView {
                    Label("No threads yet", systemImage: "bubble.left.and.bubble.right")
                } description: {
                    Text("Start a thread to send invoices or receipts to the agent from your phone.")
                } actions: {
                    Button(viewModel.isCreatingThread ? "Creating…" : "Start thread") {
                        Task {
                            selectedThread = await viewModel.createThread()
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(viewModel.isCreatingThread)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(.systemGroupedBackground))
            } else {
                List {
                    if let errorMessage = viewModel.errorMessage {
                        Section {
                            Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                                .font(.footnote)
                        }
                    }

                    Section("Threads") {
                        ForEach(viewModel.threads) { thread in
                            Button {
                                selectedThread = thread
                            } label: {
                                AgentThreadSummaryRow(thread: thread)
                            }
                            .buttonStyle(.plain)
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    deleteTarget = thread
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                            .swipeActions(edge: .leading) {
                                Button {
                                    renameTarget = thread
                                } label: {
                                    Label("Rename", systemImage: "pencil")
                                }
                                .tint(.indigo)
                            }
                        }
                    }

                    Section("Context") {
                        Label(configuration.apiBaseURL.absoluteString, systemImage: "network")
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Label(configuration.environment.displayName, systemImage: "globe")
                        if let limits = accessModel.attachmentLimits {
                            Label("Images/message: \(limits.maxImagesPerMessage)", systemImage: "photo.stack")
                            Label("Image bytes: \(limits.maxImageSizeBytes)", systemImage: "externaldrive")
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .refreshable {
                    await accessModel.reload()
                    await viewModel.reload()
                }
            }
        }
        .task {
            await accessModel.loadIfNeeded()
            await viewModel.loadIfNeeded()
            resolvePendingDeepLink()
        }
        .onChange(of: deepLink) { _, newValue in
            guard case .agentThread(let id)? = newValue else { return }
            pendingDeepLinkThreadID = id
            deepLink = nil
            resolvePendingDeepLink()
        }
        .onChange(of: viewModel.threads) { _, _ in
            resolvePendingDeepLink()
        }
        .navigationDestination(item: $selectedThread) { thread in
            AgentThreadDetailView(thread: thread, client: client, attachmentLimits: accessModel.attachmentLimits) {
                Task {
                    await viewModel.reload()
                }
            }
        }
        .sheet(item: $renameTarget) { thread in
            AgentThreadRenameSheet(initialTitle: compactThreadTitle(thread.title)) { title in
                let normalized = try validateThreadTitle(title)
                let updated = await viewModel.renameThread(threadID: thread.id, title: normalized)
                if let updated, selectedThread?.id == updated.id {
                    selectedThread = updated
                }
            }
        }
        .alert("Delete thread?", isPresented: Binding(get: { deleteTarget != nil }, set: { if !$0 { deleteTarget = nil } })) {
            Button("Delete", role: .destructive) {
                guard let deleteTarget else { return }
                Task {
                    let deleted = await viewModel.deleteThread(threadID: deleteTarget.id)
                    if deleted, selectedThread?.id == deleteTarget.id {
                        selectedThread = nil
                    }
                    self.deleteTarget = nil
                }
            }
            Button("Cancel", role: .cancel) {
                deleteTarget = nil
            }
        } message: {
            Text("Threads with running runs cannot be deleted.")
        }
        .toolbar {
            if accessModel.isAdmin {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task {
                            selectedThread = await viewModel.createThread()
                        }
                    } label: {
                        if viewModel.isCreatingThread {
                            ProgressView()
                        } else {
                            Image(systemName: "plus.circle.fill")
                        }
                    }
                    .accessibilityLabel("New thread")
                    .disabled(viewModel.isCreatingThread)
                }
            }
        }
    }

    private func resolvePendingDeepLink() {
        guard let pendingDeepLinkThreadID else { return }
        if let matched = viewModel.threads.first(where: { $0.id == pendingDeepLinkThreadID }) {
            selectedThread = matched
            self.pendingDeepLinkThreadID = nil
        }
    }
}

private extension AgentThread {
    var asThread: AgentThread {
        self
    }
}

private struct AgentThreadDetailView: View {
    let thread: AgentThreadSummary
    let client: AgentFeatureClient
    let attachmentLimits: AgentAttachmentLimits?
    let onThreadChanged: () -> Void

    @StateObject private var viewModel: AgentThreadDetailViewModel
    @State private var importedPhotoItems: [PhotosPickerItem] = []
    @State private var isFileImporterPresented = false
    @State private var renamePresented = false
    @State private var deleteConfirmationPresented = false
    @State private var selectedToolCall: AgentToolCall?
    @State private var selectedAttachment: AgentLoadedAttachment?
    @Environment(\.dismiss) private var dismiss

    init(thread: AgentThreadSummary, client: AgentFeatureClient, attachmentLimits: AgentAttachmentLimits?, onThreadChanged: @escaping () -> Void) {
        self.thread = thread
        self.client = client
        self.attachmentLimits = attachmentLimits
        self.onThreadChanged = onThreadChanged
        _viewModel = StateObject(wrappedValue: AgentThreadDetailViewModel(thread: thread, client: client, attachmentLimits: attachmentLimits))
    }

    var body: some View {
        detailContent
            .scrollDismissesKeyboard(.interactively)
            .background(Color(.systemGroupedBackground))
            .navigationTitle(compactThreadTitle(viewModel.threadTitle ?? thread.title))
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) {
                composerInset
            }
            .fileImporter(
                isPresented: $isFileImporterPresented,
                allowedContentTypes: [.pdf, .image],
                allowsMultipleSelection: true,
                onCompletion: handleFileImport
            )
            .onChange(of: importedPhotoItems) { _, newValue in
                Task {
                    await viewModel.importPhotoItems(newValue)
                    importedPhotoItems = []
                }
            }
            .task {
                await viewModel.loadIfNeeded()
            }
            .refreshable {
                await viewModel.reload()
                onThreadChanged()
            }
            .sheet(isPresented: $renamePresented) {
                renameSheet
            }
            .sheet(item: $selectedToolCall) { toolCall in
                AgentToolCallSheet(toolCall: toolCall)
            }
            .sheet(item: $selectedAttachment) { attachment in
                AgentAttachmentSheet(attachment: attachment)
            }
            .alert("Delete thread?", isPresented: $deleteConfirmationPresented) {
                Button("Delete", role: .destructive) {
                    Task {
                        let deleted = await viewModel.deleteThread()
                        if deleted {
                            onThreadChanged()
                            dismiss()
                        }
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Deleting a thread also removes its messages, runs, tool calls, and review history.")
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    threadMenu
                }
            }
    }

    private var detailContent: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 16) {
                if let errorMessage = viewModel.errorMessage, viewModel.messages.isEmpty, viewModel.sortedRuns.isEmpty {
                    ContentUnavailableView {
                        Label("Couldn’t load thread", systemImage: "wifi.exclamationmark")
                    } description: {
                        Text(errorMessage)
                    } actions: {
                        Button("Try again") {
                            Task { await viewModel.reload() }
                        }
                    }
                    .padding(.top, 48)
                } else {
                    if let sendingStatus = viewModel.sendingStatusText {
                        AgentInfoCard(
                            title: sendingStatus,
                            message: "The composer is locked while the upload and run stay in flight.",
                            symbol: "arrow.up.circle.fill",
                            tint: .indigo,
                            showsProgress: true
                        )
                    }

                    if let reviewStatus = viewModel.reviewStatusText {
                        AgentInfoCard(
                            title: "Review pending",
                            message: reviewStatus,
                            symbol: "checklist",
                            tint: .orange,
                            showsProgress: false
                        )
                    }

                    if let latestRun = viewModel.latestRun {
                        AgentRunStatusCard(
                            run: latestRun,
                            configuredModelName: viewModel.configuredModelName,
                            currentContextTokens: viewModel.currentContextTokens,
                            liveReasoning: viewModel.liveReasoning,
                            liveText: viewModel.liveText,
                            liveEvents: viewModel.liveEvents,
                            onOpenToolCall: { toolCallID in
                                Task {
                                    do {
                                        selectedToolCall = try await viewModel.loadToolCall(id: toolCallID)
                                    } catch {
                                        viewModel.actionError = error.localizedDescription
                                    }
                                }
                            }
                        )
                    }

                    if viewModel.messages.isEmpty && viewModel.sortedRuns.isEmpty {
                        AgentEmptyThreadCard()
                    } else {
                        ForEach(viewModel.messages, id: \.id) { message in
                            AgentMessageCard(message: message) { attachment in
                                Task {
                                    do {
                                        selectedAttachment = try await viewModel.loadAttachment(attachment)
                                    } catch {
                                        viewModel.actionError = error.localizedDescription
                                    }
                                }
                            }
                        }
                    }

                    if !viewModel.pendingReviewItems.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Pending review")
                                .font(.headline)

                            ForEach(viewModel.pendingReviewItems) { reviewItem in
                                AgentReviewCard(
                                    reviewItem: reviewItem,
                                    isBusy: viewModel.activeReviewItemID == reviewItem.item.id,
                                    onApprove: {
                                        Task {
                                            await viewModel.approve(itemID: reviewItem.item.id)
                                            onThreadChanged()
                                        }
                                    },
                                    onReject: {
                                        Task {
                                            await viewModel.reject(itemID: reviewItem.item.id)
                                            onThreadChanged()
                                        }
                                    },
                                    onReopen: nil
                                )
                            }
                        }
                    }

                    if !viewModel.rejectedReviewItems.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Rejected or failed")
                                .font(.headline)

                            ForEach(viewModel.rejectedReviewItems) { reviewItem in
                                AgentReviewCard(
                                    reviewItem: reviewItem,
                                    isBusy: viewModel.activeReviewItemID == reviewItem.item.id,
                                    onApprove: {},
                                    onReject: {},
                                    onReopen: {
                                        Task {
                                            await viewModel.reopen(itemID: reviewItem.item.id)
                                            onThreadChanged()
                                        }
                                    }
                                )
                            }
                        }
                    }
                }
            }
            .padding(20)
        }
    }

    private var composerInset: some View {
        AgentComposerBar(
            text: $viewModel.composerText,
            attachments: viewModel.attachments,
            isBusy: viewModel.isSending || viewModel.isImportingAttachment,
            actionError: viewModel.actionError,
            canSend: viewModel.canSend,
            maxImageSelectionCount: attachmentLimits?.maxImagesPerMessage ?? 6,
            importedPhotoItems: $importedPhotoItems,
            isFileImporterPresented: $isFileImporterPresented,
            onRemoveAttachment: viewModel.removeAttachment(id:),
            onSend: {
                Task {
                    onThreadChanged()
                    await viewModel.sendMessage()
                    onThreadChanged()
                }
            }
        )
    }

    private var renameSheet: some View {
        AgentThreadRenameSheet(initialTitle: viewModel.threadTitle ?? thread.title ?? "") { title in
            let renamed = await viewModel.renameThread(title: title)
            if renamed {
                onThreadChanged()
            }
        }
    }

    private var threadMenu: some View {
        Menu {
            Button("Rename thread") {
                renamePresented = true
            }
            Button("Delete thread", role: .destructive) {
                deleteConfirmationPresented = true
            }
        } label: {
            if viewModel.isMutatingThread {
                ProgressView()
            } else {
                Image(systemName: "ellipsis.circle")
            }
        }
    }

    private func handleFileImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            Task { await viewModel.importFileURLs(urls) }
        case .failure(let error):
            viewModel.actionError = error.localizedDescription
        }
    }
}

private struct AgentThreadSummaryRow: View {
    let thread: AgentThreadSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(compactThreadTitle(thread.title))
                    .font(.headline)
                    .foregroundStyle(.primary)
                if thread.hasRunningRun {
                    ProgressView()
                        .controlSize(.small)
                }
                Spacer()
                Text(relativeTimestamp(thread.updatedAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let preview = thread.lastMessagePreview, !preview.isEmpty {
                Text(preview)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            } else {
                Text("No messages yet")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 8) {
                if thread.pendingChangeCount > 0 {
                    AgentPill(text: "\(thread.pendingChangeCount) pending", tint: .orange)
                }
                if thread.hasRunningRun {
                    AgentPill(text: "Running", tint: .indigo)
                }
            }
        }
        .padding(.vertical, 6)
    }
}

private struct AgentMessageCard: View {
    let message: AgentMessage
    let onOpenAttachment: (AgentMessageAttachment) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label(roleTitle(message.role), systemImage: roleSymbol(message.role))
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text(relativeTimestamp(message.createdAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Group {
                if let renderedContent = AssistantMessageMarkdownRenderer.renderedContent(for: message) {
                    Text(renderedContent)
                } else {
                    Text(messageContent(message))
                }
            }
            .font(.body)
            .textSelection(.enabled)

            if !message.attachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(message.attachments, id: \.id) { attachment in
                            Button {
                                onOpenAttachment(attachment)
                            } label: {
                                Label(attachmentName(attachment), systemImage: attachment.mimeType == "application/pdf" ? "doc.richtext" : "photo")
                                    .font(.caption.weight(.medium))
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(Color.secondary.opacity(0.12), in: Capsule())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(backgroundColor(message.role), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

private struct AgentRunStatusCard: View {
    let run: AgentRun
    let configuredModelName: String
    let currentContextTokens: Int?
    let liveReasoning: String
    let liveText: String
    let liveEvents: [AgentRunEvent]
    let onOpenToolCall: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                AgentPill(text: runStatusText(run.status), tint: runStatusTint(run.status))
                Text((run.modelName.isEmpty ? configuredModelName : run.modelName).isEmpty ? "Agent" : (run.modelName.isEmpty ? configuredModelName : run.modelName))
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text(relativeTimestamp(run.createdAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let errorText = run.errorText, !errorText.isEmpty {
                Text(errorText)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            if let currentContextTokens {
                Text("Context tokens: \(currentContextTokens)")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 12) {
                Text("Surface: \(run.surface)")
                Text("Reply: \(run.replySurface)")
                if let totalCostUsd = run.totalCostUsd {
                    Text(totalCostUsd.formatted(.currency(code: "USD")))
                }
            }
            .font(.footnote)
            .foregroundStyle(.secondary)

            if !liveText.isEmpty {
                Text(liveText)
                    .font(.body)
            }

            if !liveReasoning.isEmpty {
                Text(liveReasoning)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            if !liveEvents.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(liveEvents.suffix(4)), id: \.id) { event in
                        if let toolCallID = event.toolCallId {
                            Button {
                                onOpenToolCall(toolCallID)
                            } label: {
                                Label(event.message ?? readableEventType(event.eventType), systemImage: "sparkle")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                        } else {
                            Label(event.message ?? readableEventType(event.eventType), systemImage: "sparkle")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            if let terminalAssistantReply = run.terminalAssistantReply, !terminalAssistantReply.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Terminal reply")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Text(terminalAssistantReply)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }

            if !run.toolCalls.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Tool calls")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    ForEach(run.toolCalls, id: \.id) { toolCall in
                        Button {
                            onOpenToolCall(toolCall.id)
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(toolCall.toolName)
                                        .font(.footnote.weight(.semibold))
                                        .foregroundStyle(.primary)
                                    Text(toolCall.status.rawValue.uppercased())
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                if toolCall.hasFullPayload {
                                    Text("Open")
                                        .font(.caption)
                                        .foregroundStyle(.indigo)
                                } else {
                                    Text("Hydrate")
                                        .font(.caption)
                                        .foregroundStyle(.indigo)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.indigo.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

private struct AgentReviewCard: View {
    let reviewItem: AgentReviewItem
    let isBusy: Bool
    let onApprove: () -> Void
    let onReject: () -> Void
    let onReopen: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                AgentPill(text: changeTypeLabel(reviewItem.item.changeType), tint: .orange)
                Spacer()
                Text(relativeTimestamp(reviewItem.item.createdAt))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(reviewSummary(reviewItem.item))
                .font(.headline)

            if !reviewItem.item.rationaleText.isEmpty {
                Text(reviewItem.item.rationaleText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            Text(payloadPreview(reviewItem.item.payloadJson))
                .font(.footnote.monospaced())
                .foregroundStyle(.secondary)
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            HStack {
                if reviewItem.item.status == .pendingReview {
                    Button("Reject", action: onReject)
                        .buttonStyle(.bordered)
                        .tint(.red)
                        .disabled(isBusy)
                    Button(isBusy ? "Approving…" : "Approve", action: onApprove)
                        .buttonStyle(.borderedProminent)
                        .disabled(isBusy)
                } else if let onReopen {
                    Button(isBusy ? "Reopening…" : "Reopen") {
                        onReopen()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy)
                }
                Spacer()
                Text("Run \(shortID(reviewItem.run.id))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

private struct AgentComposerBar: View {
    @Binding var text: String
    let attachments: [ComposerAttachment]
    let isBusy: Bool
    let actionError: String?
    let canSend: Bool
    let maxImageSelectionCount: Int
    @Binding var importedPhotoItems: [PhotosPickerItem]
    @Binding var isFileImporterPresented: Bool
    let onRemoveAttachment: (UUID) -> Void
    let onSend: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !attachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(attachments) { attachment in
                            HStack(spacing: 6) {
                                Label(attachment.filename, systemImage: attachment.mimeType == "application/pdf" ? "doc" : "photo")
                                    .lineLimit(1)
                                Button {
                                    onRemoveAttachment(attachment.id)
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                }
                                .buttonStyle(.plain)
                                .disabled(isBusy)
                            }
                            .font(.caption.weight(.medium))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(Color.secondary.opacity(0.12), in: Capsule())
                        }
                    }
                }
            }

            TextField("Ask the agent to review an invoice or receipt…", text: $text, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1 ... 4)
                .disabled(isBusy)

            HStack(spacing: 12) {
                PhotosPicker(selection: $importedPhotoItems, maxSelectionCount: maxImageSelectionCount, matching: .images) {
                    Label("Photo", systemImage: "photo.on.rectangle")
                }
                .disabled(isBusy)

                Button {
                    isFileImporterPresented = true
                } label: {
                    Label("PDF / File", systemImage: "doc.badge.plus")
                }
                .disabled(isBusy)

                Spacer()

                Button(action: onSend) {
                    Label(isBusy ? "Sending" : "Send", systemImage: "arrow.up.circle.fill")
                }
                .buttonStyle(.borderedProminent)
                .disabled(!canSend)
            }
            .font(.subheadline.weight(.medium))

            if let actionError, !actionError.isEmpty {
                Label(actionError, systemImage: "exclamationmark.triangle.fill")
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
        }
        .padding(16)
        .background(.regularMaterial)
        .overlay(alignment: .top) {
            Divider()
        }
    }
}

private struct AgentInfoCard: View {
    let title: String
    let message: String
    let symbol: String
    let tint: Color
    let showsProgress: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            if showsProgress {
                ProgressView()
                    .tint(tint)
            } else {
                Image(systemName: symbol)
                    .foregroundStyle(tint)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text(title)
                    .font(.headline)
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

private struct AgentEmptyThreadCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Ready for receipts and invoices", systemImage: "tray.and.arrow.up.fill")
                .font(.headline)
            Text("Send a note, attach one or more files, and the agent will respond here with run progress and any proposals that need review.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct AgentAccessRequiredView: View {
    let principalName: String?

    var body: some View {
        ContentUnavailableView {
            Label("Agent access required", systemImage: "lock.fill")
        } description: {
            Text("\(principalName ?? "This principal") does not have admin access, so the agent thread and review routes stay unavailable.")
        } actions: {
            Link(destination: URL(string: "billhelper://settings")!) {
                Label("Switch principal in Settings", systemImage: "gearshape")
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

private struct AgentThreadRenameSheet: View {
    let initialTitle: String
    let onSave: (String) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(initialTitle: String, onSave: @escaping (String) async throws -> Void) {
        self.initialTitle = initialTitle
        self.onSave = onSave
        _title = State(initialValue: initialTitle)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Title") {
                    TextField("1-5 words", text: $title)
                    Text("\(title.trimmingCharacters(in: .whitespacesAndNewlines).count)/\(threadTitleMaxLength) characters")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if let errorMessage {
                    Section {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("Rename Thread")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        do {
            let normalized = try validateThreadTitle(title)
            try await onSave(normalized)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct AgentToolCallSheet: View {
    let toolCall: AgentToolCall

    var body: some View {
        NavigationStack {
            List {
                Section("Overview") {
                    LabeledContent("Tool", value: toolCall.toolName)
                    LabeledContent("Status", value: toolCall.status.rawValue.uppercased())
                    LabeledContent("Queued", value: relativeTimestamp(toolCall.createdAt))
                }

                if let inputJson = toolCall.inputJson {
                    Section("Input") {
                        Text(prettyJSONPreview(inputJson))
                            .font(.footnote.monospaced())
                            .textSelection(.enabled)
                    }
                }

                if let outputJson = toolCall.outputJson {
                    Section("Output JSON") {
                        Text(prettyJSONPreview(outputJson))
                            .font(.footnote.monospaced())
                            .textSelection(.enabled)
                    }
                }

                if let outputText = toolCall.outputText, !outputText.isEmpty {
                    Section("Output Text") {
                        Text(outputText)
                            .font(.footnote)
                            .textSelection(.enabled)
                    }
                }
            }
            .navigationTitle(toolCall.toolName)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct AgentAttachmentSheet: View {
    let attachment: AgentLoadedAttachment

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let image = attachment.image {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    } else {
                        Label("Preview unavailable", systemImage: attachment.resource.mimeType == "application/pdf" ? "doc.richtext" : "doc")
                            .font(.headline)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text(attachment.resource.fileName)
                            .font(.headline)
                        Text(attachment.resource.mimeType)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        Text("\(attachment.resource.data.count) bytes")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }

                    ShareLink(item: attachment.url) {
                        Label("Download or share", systemImage: "square.and.arrow.down")
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding(20)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Attachment")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct AgentPill: View {
    let text: String
    let tint: Color

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(tint.opacity(0.14), in: Capsule())
            .foregroundStyle(tint)
    }
}

struct ComposerAttachment: Identifiable, Equatable {
    let id = UUID()
    let upload: AttachmentUpload

    var filename: String { upload.filename }
    var mimeType: String { upload.mimeType }
}

struct AgentReviewItem: Identifiable, Equatable {
    let run: AgentRun
    let item: AgentChangeItem

    var id: String { item.id }
}

struct AgentLoadedAttachment: Identifiable, Equatable {
    let id = UUID()
    let resource: AgentAttachmentResource
    let url: URL
    let image: UIImage?

    init(resource: AgentAttachmentResource) throws {
        self.resource = resource
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("billhelper-agent-attachments", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let preferredName = resource.fileName.isEmpty ? UUID().uuidString : resource.fileName
        let url = directory.appendingPathComponent(preferredName)
        try resource.data.write(to: url, options: .atomic)
        self.url = url
        if resource.mimeType.hasPrefix("image/") {
            image = UIImage(data: resource.data)
        } else {
            image = nil
        }
    }
}

private enum AttachmentImportError: LocalizedError {
    case unreadableAsset
    case tooManyImages(limit: Int)
    case imageTooLarge(limit: Int)

    var errorDescription: String? {
        switch self {
        case .unreadableAsset:
            return "One of the selected attachments could not be read."
        case .tooManyImages(let limit):
            return "You can attach at most \(limit) images per message."
        case .imageTooLarge(let limit):
            return "One of the selected images exceeds the \(limit)-byte size limit."
        }
    }
}

extension AgentThreadSummary: Identifiable {}

private func compactThreadTitle(_ title: String?) -> String {
    let trimmed = title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    return trimmed.isEmpty ? "Untitled thread" : trimmed
}

private func validateThreadTitle(_ value: String) throws -> String {
    let normalized = value
        .split(whereSeparator: \.isWhitespace)
        .map(String.init)
        .joined(separator: " ")
        .trimmingCharacters(in: .whitespacesAndNewlines)
    guard !normalized.isEmpty else {
        throw APIError.requestFailed(statusCode: 422, message: "thread title cannot be empty")
    }
    guard normalized.count <= threadTitleMaxLength else {
        throw APIError.requestFailed(statusCode: 422, message: "thread title must be \(threadTitleMaxLength) characters or fewer")
    }
    guard normalized.split(separator: " ").count <= threadTitleMaxWords else {
        throw APIError.requestFailed(statusCode: 422, message: "thread title must be \(threadTitleMaxWords) words or fewer")
    }
    return normalized
}

private func roleTitle(_ role: AgentMessageRole) -> String {
    switch role {
    case .assistant: "Agent"
    case .system: "System"
    case .user: "You"
    }
}

private func roleSymbol(_ role: AgentMessageRole) -> String {
    switch role {
    case .assistant: "sparkles"
    case .system: "gearshape.2"
    case .user: "person.fill"
    }
}

private func backgroundColor(_ role: AgentMessageRole) -> Color {
    switch role {
    case .assistant: Color.indigo.opacity(0.08)
    case .system: Color.secondary.opacity(0.10)
    case .user: Color.green.opacity(0.10)
    }
}

enum AssistantMessageMarkdownRenderer {
    static func renderedContent(for message: AgentMessage) -> AttributedString? {
        guard message.role == .assistant else { return nil }

        let content = messageContent(message)
        do {
            return try AttributedString(markdown: content)
        } catch {
            agentMessageMarkdownLogger.error(
                "Failed to parse assistant markdown for message \(message.id, privacy: .public): \(String(describing: error), privacy: .public)"
            )
            return nil
        }
    }
}

private func messageContent(_ message: AgentMessage) -> String {
    let trimmed = message.contentMarkdown.trimmingCharacters(in: .whitespacesAndNewlines)
    if !trimmed.isEmpty {
        return trimmed
    }
    return message.attachments.isEmpty ? "No message text." : "Attachment uploaded"
}

private func attachmentName(_ attachment: AgentMessageAttachment) -> String {
    let path = attachment.filePath.split(separator: "/").last.map(String.init) ?? attachment.id
    return path.isEmpty ? attachment.id : path
}

private enum AgentDateFormatters {
    nonisolated(unsafe) static let fractionalISO8601: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    nonisolated(unsafe) static let basicISO8601: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()
}

private func relativeTimestamp(_ value: String) -> String {
    let date = AgentDateFormatters.fractionalISO8601.date(from: value) ?? AgentDateFormatters.basicISO8601.date(from: value)
    guard let date else { return value }
    return date.formatted(.relative(presentation: .named))
}

private func runStatusText(_ status: AgentRunStatus) -> String {
    switch status {
    case .running: "Running"
    case .completed: "Completed"
    case .failed: "Failed"
    }
}

private func runStatusTint(_ status: AgentRunStatus) -> Color {
    switch status {
    case .running: .indigo
    case .completed: .green
    case .failed: .red
    }
}

private func readableEventType(_ eventType: AgentRunEventType) -> String {
    switch eventType {
    case .runStarted: "Run started"
    case .reasoningUpdate: "Reasoning update"
    case .toolCallQueued: "Tool queued"
    case .toolCallStarted: "Tool started"
    case .toolCallCompleted: "Tool completed"
    case .toolCallFailed: "Tool failed"
    case .toolCallCancelled: "Tool cancelled"
    case .runCompleted: "Run completed"
    case .runFailed: "Run failed"
    }
}

private func changeTypeLabel(_ changeType: AgentChangeType) -> String {
    switch changeType {
    case .createEntry: "Create Entry"
    case .updateEntry: "Update Entry"
    case .deleteEntry: "Delete Entry"
    case .createAccount: "Create Account"
    case .updateAccount: "Update Account"
    case .deleteAccount: "Delete Account"
    case .createGroup: "Create Group"
    case .updateGroup: "Update Group"
    case .deleteGroup: "Delete Group"
    case .createGroupMember: "Create Group Member"
    case .deleteGroupMember: "Delete Group Member"
    case .createTag: "Create Tag"
    case .updateTag: "Update Tag"
    case .deleteTag: "Delete Tag"
    case .createEntity: "Create Entity"
    case .updateEntity: "Update Entity"
    case .deleteEntity: "Delete Entity"
    }
}

private func reviewSummary(_ item: AgentChangeItem) -> String {
    switch item.changeType {
    case .createEntry:
        let name = item.payloadJson["name"]?.stringValue ?? "Untitled"
        let date = item.payloadJson["date"]?.stringValue ?? "unknown date"
        return "Create entry: \(name) on \(date)"
    case .updateEntry, .deleteEntry:
        let selectorName = item.payloadJson["selector"]?.objectValue?["name"]?.stringValue ?? "Unknown entry"
        return "\(changeTypeLabel(item.changeType)): \(selectorName)"
    case .createAccount, .deleteAccount:
        let name = item.payloadJson["name"]?.stringValue ?? "Untitled"
        return "\(changeTypeLabel(item.changeType)): \(name)"
    case .updateAccount:
        let name = item.payloadJson["name"]?.stringValue ?? "Untitled"
        return "\(changeTypeLabel(item.changeType)): \(name)"
    case .createGroup, .deleteGroup:
        let name = item.payloadJson["name"]?.stringValue ?? "Untitled group"
        return "\(changeTypeLabel(item.changeType)): \(name)"
    case .updateGroup:
        let groupID = item.payloadJson["group_id"]?.stringValue ?? "Unknown group"
        return "Update Group: \(groupID)"
    case .createGroupMember, .deleteGroupMember:
        let groupName = item.payloadJson["group_preview"]?.objectValue?["name"]?.stringValue
            ?? item.payloadJson["group_ref"]?.objectValue?["group_id"]?.stringValue
            ?? "Unknown group"
        let memberName = item.payloadJson["member_preview"]?.objectValue?["name"]?.stringValue
            ?? item.payloadJson["entry_ref"]?.objectValue?["entry_id"]?.stringValue
            ?? "Unknown entry"
        return "\(changeTypeLabel(item.changeType)): \(memberName) in \(groupName)"
    case .createTag, .deleteTag, .createEntity, .deleteEntity:
        let name = item.payloadJson["name"]?.stringValue ?? "Untitled"
        return "\(changeTypeLabel(item.changeType)): \(name)"
    case .updateTag, .updateEntity:
        let name = item.payloadJson["name"]?.stringValue ?? "Untitled"
        return "\(changeTypeLabel(item.changeType)): \(name)"
    }
}

private func payloadPreview(_ payload: [String: JSONValue]) -> String {
    guard let data = try? JSONEncoder.billHelper.encode(payload),
          let text = String(data: data, encoding: .utf8) else {
        return "{}"
    }
    return text
}

private func prettyJSONPreview(_ payload: [String: JSONValue]) -> String {
    guard let data = try? JSONEncoder.billHelper.encode(payload),
          let object = try? JSONSerialization.jsonObject(with: data),
          let prettyData = try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted]),
          let text = String(data: prettyData, encoding: .utf8) else {
        return payloadPreview(payload)
    }
    return text
}

private func shortID(_ value: String) -> String {
    String(value.prefix(8))
}

private extension JSONValue {
    var stringValue: String? {
        if case .string(let value) = self {
            return value
        }
        return nil
    }

    var objectValue: [String: JSONValue]? {
        if case .object(let value) = self {
            return value
        }
        return nil
    }
}
