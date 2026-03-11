#if canImport(MarkdownUI)
import MarkdownUI
#endif
import SwiftUI
import os

let agentMessageMarkdownLogger = Logger(subsystem: "com.billhelper.ios", category: "AgentMessageMarkdown")

struct AgentRenderedMarkdown: Equatable {
    let markdown: String?
    let fallbackText: String
}

struct AgentMarkdownText: View {
    let rendered: AgentRenderedMarkdown
    var tint: Color = .indigo

    var body: some View {
        Group {
            if let markdown = rendered.markdown {
#if canImport(MarkdownUI)
                Markdown(markdown)
                    .foregroundStyle(agentMarkdownForegroundColor(for: tint))
                    .markdownTextStyle(\.link) {
                        ForegroundColor(tint)
                    }
                    .markdownTextStyle(\.code) {
                        FontFamilyVariant(.monospaced)
                        FontSize(.em(0.88))
                        ForegroundColor(agentMarkdownForegroundColor(for: tint))
                        BackgroundColor(tint.opacity(0.12))
                    }
                    .markdownBlockStyle(\.paragraph) { configuration in
                        configuration.label
                            .relativeLineSpacing(.em(0.2))
                            .markdownMargin(top: 0, bottom: 14)
                    }
                    .markdownBlockStyle(\.listItem) { configuration in
                        configuration.label
                            .markdownMargin(top: .em(0.18))
                    }
                    .markdownBlockStyle(\.blockquote) { configuration in
                        configuration.label
                            .padding(.vertical, 8)
                            .padding(.horizontal, 12)
                            .markdownTextStyle {
                                ForegroundColor(agentMarkdownForegroundColor(for: tint))
                                BackgroundColor(nil)
                            }
                            .overlay(alignment: .leading) {
                                Capsule()
                                    .fill(tint.opacity(0.45))
                                    .frame(width: 4)
                            }
                            .background(tint.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
#else
                if let attributed = try? AttributedString(markdown: markdown) {
                    Text(attributed)
                } else {
                    Text(rendered.fallbackText)
                }
#endif
            } else {
                Text(rendered.fallbackText)
            }
        }
        .tint(tint)
        .textSelection(.enabled)
    }
}

private func agentMarkdownForegroundColor(for tint: Color) -> Color {
    tint.opacity(0.96)
}

enum AssistantMessageMarkdownRenderer {
    static func renderedContent(for message: AgentMessage) -> AgentRenderedMarkdown? {
        guard message.role == .assistant else { return nil }
        return renderedContent(forMarkdown: messageContent(message), messageID: message.id)
    }

    static func renderedContent(forMarkdown markdown: String, messageID: String) -> AgentRenderedMarkdown {
        let fallbackText = markdown.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "No message text." : markdown
        let normalized = normalizedMarkdown(markdown)
        guard !normalized.isEmpty else {
            return AgentRenderedMarkdown(markdown: nil, fallbackText: fallbackText)
        }

        if containsUnsupportedControlCharacters(normalized) {
            agentMessageMarkdownLogger.error(
                "Falling back to plain text for message \(messageID, privacy: .public) because the markdown contains unsupported control characters."
            )
            return AgentRenderedMarkdown(markdown: nil, fallbackText: fallbackText)
        }

        do {
            _ = try AttributedString(markdown: normalized)
            return AgentRenderedMarkdown(markdown: normalized, fallbackText: fallbackText)
        } catch {
            agentMessageMarkdownLogger.error(
                "Failed to preflight assistant markdown for message \(messageID, privacy: .public): \(String(describing: error), privacy: .public)"
            )
            return AgentRenderedMarkdown(markdown: nil, fallbackText: fallbackText)
        }
    }

    static func normalizedMarkdown(_ raw: String) -> String {
        let sanitized = raw
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")
            .replacingOccurrences(of: "\u{00A0}", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard !sanitized.isEmpty else { return "" }

        let lines = sanitized.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        var normalized: [String] = []
        var isInsideFence = false
        var previousWasBlank = true

        for rawLine in lines {
            let trimmed = rawLine.trimmingCharacters(in: .whitespaces)

            if trimmed.hasPrefix("```") {
                if !previousWasBlank {
                    normalized.append("")
                }
                normalized.append(trimmed)
                previousWasBlank = false
                isInsideFence.toggle()
                continue
            }

            if isInsideFence {
                normalized.append(rawLine)
                previousWasBlank = false
                continue
            }

            if trimmed.isEmpty {
                if !previousWasBlank {
                    normalized.append("")
                }
                previousWasBlank = true
                continue
            }

            let startsBlock = startsMarkdownBlock(trimmed)
            if startsBlock && !previousWasBlank && !continuesMarkdownBlock(currentLine: trimmed, previousLine: normalized.last ?? "") {
                normalized.append("")
            } else if let previous = normalized.last, needsParagraphBreak(before: trimmed, previousLine: previous) {
                normalized.append("")
            }

            normalized.append(trimmed)
            previousWasBlank = false
        }

        while normalized.last == "" {
            normalized.removeLast()
        }

        return normalized.joined(separator: "\n")
    }

    private static func startsMarkdownBlock(_ line: String) -> Bool {
        line.hasPrefix("#")
            || line.hasPrefix("> ")
            || isListLine(line)
            || line == "---"
            || line == "***"
    }

    private static func needsParagraphBreak(before currentLine: String, previousLine: String) -> Bool {
        guard !previousLine.isEmpty else { return false }

        let previousWasList = isListLine(previousLine)
            || previousLine.hasPrefix("> ")
        let currentStartsParagraph = !startsMarkdownBlock(currentLine)

        return previousWasList && currentStartsParagraph
    }

    private static func continuesMarkdownBlock(currentLine: String, previousLine: String) -> Bool {
        (isListLine(currentLine) && isListLine(previousLine))
            || (currentLine.hasPrefix("> ") && previousLine.hasPrefix("> "))
    }

    private static func isListLine(_ line: String) -> Bool {
        line.hasPrefix("- ")
            || line.hasPrefix("* ")
            || line.range(of: #"^\d+\.\s"#, options: .regularExpression) != nil
    }

    private static func containsUnsupportedControlCharacters(_ value: String) -> Bool {
        value.unicodeScalars.contains { scalar in
            switch scalar.value {
            case 9, 10:
                return false
            default:
                return scalar.properties.generalCategory == .control
            }
        }
    }
}
