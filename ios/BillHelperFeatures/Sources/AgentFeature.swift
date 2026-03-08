import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

struct AgentFeatureClient {
    var listThreads: () async throws -> [AgentThreadSummary]
    var createThread: (_ title: String?) async throws -> AgentThread
    var loadThread: (_ threadId: String) async throws -> AgentThreadDetail
    var startMessageRun: (_ threadId: String, _ content: String, _ attachments: [AttachmentUpload]) -> AsyncThrowingStream<AgentRunUpdate, Error>
    var approveChange: (_ itemId: String) async throws -> AgentChangeItem
    var rejectChange: (_ itemId: String) async throws -> AgentChangeItem

    static func live(apiClient: APIClient, transport: AgentRunTransport) -> AgentFeatureClient {
        AgentFeatureClient(
            listThreads: { try await apiClient.listAgentThreads() },
            createThread: { try await apiClient.createAgentThread(title: $0) },
            loadThread: { try await apiClient.agentThread(id: $0) },
            startMessageRun: { transport.startMessageRun(threadId: $0, content: $1, attachments: $2) },
            approveChange: { try await apiClient.approveChangeItem(id: $0) },
            rejectChange: { try await apiClient.rejectChangeItem(id: $0) }
        )
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

    let threadID: String

    private let client: AgentFeatureClient
    private var hasLoaded = false

    init(thread: AgentThreadSummary, client: AgentFeatureClient) {
        threadID = thread.id
        threadTitle = thread.title
        self.client = client
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
            status: run.status,
            modelName: run.modelName,
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
}

struct AgentRootView: View {
    let configuration: AppConfiguration
    let client: AgentFeatureClient

    @StateObject private var viewModel: AgentThreadListViewModel
    @State private var selectedThread: AgentThreadSummary?

    init(configuration: AppConfiguration, client: AgentFeatureClient) {
        self.configuration = configuration
        self.client = client
        _viewModel = StateObject(wrappedValue: AgentThreadListViewModel(client: client))
    }

    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.threads.isEmpty {
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
                        }
                    }

                    Section("Context") {
                        Label(configuration.apiBaseURL.absoluteString, systemImage: "network")
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Label(configuration.environment.displayName, systemImage: "globe")
                    }
                }
                .listStyle(.insetGrouped)
                .refreshable {
                    await viewModel.reload()
                }
            }
        }
        .task {
            await viewModel.loadIfNeeded()
        }
        .navigationDestination(item: $selectedThread) { thread in
            AgentThreadDetailView(thread: thread, client: client) {
                Task {
                    await viewModel.reload()
                }
            }
        }
        .toolbar {
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

private struct AgentThreadDetailView: View {
    let thread: AgentThreadSummary
    let client: AgentFeatureClient
    let onThreadChanged: () -> Void

    @StateObject private var viewModel: AgentThreadDetailViewModel
    @State private var importedPhotoItems: [PhotosPickerItem] = []
    @State private var isFileImporterPresented = false

    init(thread: AgentThreadSummary, client: AgentFeatureClient, onThreadChanged: @escaping () -> Void) {
        self.thread = thread
        self.client = client
        self.onThreadChanged = onThreadChanged
        _viewModel = StateObject(wrappedValue: AgentThreadDetailViewModel(thread: thread, client: client))
    }

    var body: some View {
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
                            liveEvents: viewModel.liveEvents
                        )
                    }

                    if viewModel.messages.isEmpty && viewModel.sortedRuns.isEmpty {
                        AgentEmptyThreadCard()
                    } else {
                        ForEach(viewModel.messages, id: \.id) { message in
                            AgentMessageCard(message: message)
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
                                    }
                                )
                            }
                        }
                    }
                }
            }
            .padding(20)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Color(.systemGroupedBackground))
        .navigationTitle(compactThreadTitle(viewModel.threadTitle ?? thread.title))
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            AgentComposerBar(
                text: $viewModel.composerText,
                attachments: viewModel.attachments,
                isBusy: viewModel.isSending || viewModel.isImportingAttachment,
                actionError: viewModel.actionError,
                canSend: viewModel.canSend,
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
        .fileImporter(
            isPresented: $isFileImporterPresented,
            allowedContentTypes: [.pdf, .image],
            allowsMultipleSelection: true
        ) { result in
            switch result {
            case .success(let urls):
                Task { await viewModel.importFileURLs(urls) }
            case .failure(let error):
                viewModel.actionError = error.localizedDescription
            }
        }
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

            Text(messageContent(message))
                .font(.body)
                .textSelection(.enabled)

            if !message.attachments.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(message.attachments, id: \.id) { attachment in
                            Label(attachmentName(attachment), systemImage: attachment.mimeType == "application/pdf" ? "doc.richtext" : "photo")
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
                        Label(event.message ?? readableEventType(event.eventType), systemImage: "sparkle")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
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
                Button("Reject", action: onReject)
                    .buttonStyle(.bordered)
                    .tint(.red)
                    .disabled(isBusy)
                Button(isBusy ? "Approving…" : "Approve", action: onApprove)
                    .buttonStyle(.borderedProminent)
                    .disabled(isBusy)
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
                PhotosPicker(selection: $importedPhotoItems, maxSelectionCount: 6, matching: .images) {
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

private enum AttachmentImportError: LocalizedError {
    case unreadableAsset

    var errorDescription: String? {
        switch self {
        case .unreadableAsset:
            return "One of the selected attachments could not be read."
        }
    }
}

extension AgentThreadSummary: Identifiable {}

private func compactThreadTitle(_ title: String?) -> String {
    let trimmed = title?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    return trimmed.isEmpty ? "Untitled thread" : trimmed
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