import PhotosUI
import SwiftUI
import UIKit

enum AgentFeedback {
    @MainActor
    static func success() {
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    @MainActor
    static func warning() {
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
    }

    @MainActor
    static func error() {
        UINotificationFeedbackGenerator().notificationOccurred(.error)
    }

    @MainActor
    static func impact() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
}

struct AgentPill: View {
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

struct AgentInfoCard: View {
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
                    .accessibilityHidden(true)
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

struct AgentComposerAttachmentChip: View {
    let attachment: ComposerAttachment
    let isBusy: Bool
    let onRemove: (UUID) -> Void

    var body: some View {
        HStack(spacing: 8) {
            Label(attachment.filename, systemImage: attachment.mimeType == "application/pdf" ? "doc" : "photo")
                .lineLimit(1)
            Button {
                onRemove(attachment.id)
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            .disabled(isBusy)
            .accessibilityLabel("Remove \(attachment.filename)")
        }
        .font(.caption.weight(.medium))
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.secondary.opacity(0.12), in: Capsule())
    }
}

struct AgentComposerBar: View {
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
                            AgentComposerAttachmentChip(attachment: attachment, isBusy: isBusy, onRemove: onRemoveAttachment)
                        }
                    }
                    .padding(.horizontal, 2)
                }
            }

            TextField("Ask the agent to review an invoice or receipt…", text: $text, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1 ... 5)
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

                Button {
                    AgentFeedback.impact()
                    onSend()
                } label: {
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

struct AgentToolCallSheet: View {
    let toolCall: AgentToolCall

    var body: some View {
        NavigationStack {
            List {
                Section("Overview") {
                    LabeledContent("Tool", value: toolCall.toolName)
                    LabeledContent("Status", value: toolCall.status.rawValue.uppercased())
                    LabeledContent("Queued", value: agentRelativeTimestamp(toolCall.createdAt))
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
                        AgentMarkdownText(rendered: AssistantMessageMarkdownRenderer.renderedContent(forMarkdown: outputText, messageID: toolCall.id))
                            .font(.footnote)
                    }
                }
            }
            .navigationTitle(toolCall.toolName)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct AgentAttachmentSheet: View {
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
