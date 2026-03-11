import Foundation

struct AgentAttachmentResource: Equatable, Sendable {
    let data: Data
    let mimeType: String
    let fileName: String
}

extension APIClient {
    func renameAgentThread(id: String, title: String) async throws -> AgentThread {
        struct RequestBody: Encodable {
            let title: String
        }

        return try await perform(
            path: "/agent/threads/\(id)",
            method: "PATCH",
            body: try encoder.encode(RequestBody(title: title))
        )
    }

    func deleteAgentThread(id: String) async throws {
        _ = try await performWithoutResponse(path: "/agent/threads/\(id)", method: "DELETE")
    }

    func reopenChangeItem(
        id: String,
        note: String? = nil,
        payloadOverride: [String: JSONValue]? = nil
    ) async throws -> AgentChangeItem {
        struct RequestBody: Encodable {
            let note: String?
            let payloadOverride: [String: JSONValue]?
        }

        return try await perform(
            path: "/agent/change-items/\(id)/reopen",
            method: "POST",
            body: try encoder.encode(RequestBody(note: note, payloadOverride: payloadOverride))
        )
    }

    func agentToolCall(id: String) async throws -> AgentToolCall {
        try await perform(path: "/agent/tool-calls/\(id)")
    }

    func agentAttachment(id: String) async throws -> AgentAttachmentResource {
        let response = try await performWithoutResponse(path: "/agent/attachments/\(id)")
        let mimeType = response.headers["Content-Type"] as? String ?? "application/octet-stream"
        let fileName = Self.sanitizedFilename(Self.filename(from: response.headers["Content-Disposition"] as? String)) ?? id
        return AgentAttachmentResource(data: response.data, mimeType: mimeType, fileName: fileName)
    }

    private static func filename(from contentDisposition: String?) -> String? {
        guard let contentDisposition else { return nil }
        let parts = contentDisposition.split(separator: ";")
        for part in parts {
            let trimmed = part.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix("filename=") else { continue }
            return trimmed
                .replacingOccurrences(of: "filename=", with: "")
                .trimmingCharacters(in: CharacterSet(charactersIn: "\""))
        }
        return nil
    }

    private static func sanitizedFilename(_ fileName: String?) -> String? {
        guard let fileName else { return nil }
        let normalized = fileName
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "\\", with: "/")
        let lastPathComponent = (normalized as NSString).lastPathComponent
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !lastPathComponent.isEmpty, lastPathComponent != ".", lastPathComponent != ".." else {
            return nil
        }
        return lastPathComponent
    }
}
