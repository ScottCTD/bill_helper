import Foundation

enum APIError: LocalizedError, Equatable {
    case invalidURL(String)
    case invalidResponse
    case requestFailed(statusCode: Int, message: String)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let path):
            return "Invalid API URL for path: \(path)"
        case .invalidResponse:
            return "The server returned an invalid response."
        case .requestFailed(_, let message):
            return message
        }
    }
}

struct HTTPResponse: @unchecked Sendable {
    let data: Data
    let statusCode: Int
    let headers: [AnyHashable: Any]
}

struct HTTPResponseStream: @unchecked Sendable {
    let statusCode: Int
    let headers: [AnyHashable: Any]
    let chunks: AsyncThrowingStream<Data, Error>
}

protocol HTTPTransport {
    func response(for request: URLRequest) async throws -> HTTPResponse
    func stream(for request: URLRequest) async throws -> HTTPResponseStream
}

struct URLSessionHTTPTransport: HTTPTransport {
    let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func response(for request: URLRequest) async throws -> HTTPResponse {
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        return HTTPResponse(data: data, statusCode: httpResponse.statusCode, headers: httpResponse.allHeaderFields)
    }

    func stream(for request: URLRequest) async throws -> HTTPResponseStream {
        let (bytes, response) = try await session.bytes(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        let chunks = AsyncThrowingStream<Data, Error> { continuation in
            let task = Task {
                do {
                    var chunk = Data()
                    for try await byte in bytes {
                        chunk.append(byte)
                        if byte == 10 || chunk.count >= 1024 {
                            continuation.yield(chunk)
                            chunk.removeAll(keepingCapacity: true)
                        }
                    }
                    if !chunk.isEmpty {
                        continuation.yield(chunk)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }

        return HTTPResponseStream(statusCode: httpResponse.statusCode, headers: httpResponse.allHeaderFields, chunks: chunks)
    }
}

struct APIClient: @unchecked Sendable {
    private let baseURL: URL
    private let transport: HTTPTransport
    private let sessionProvider: SessionProviding?
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(
        baseURL: URL,
        transport: HTTPTransport = URLSessionHTTPTransport(),
        sessionProvider: SessionProviding? = nil,
        decoder: JSONDecoder = .billHelper,
        encoder: JSONEncoder = .billHelper
    ) {
        self.baseURL = baseURL
        self.transport = transport
        self.sessionProvider = sessionProvider
        self.decoder = decoder
        self.encoder = encoder
    }

    func dashboard(month: String) async throws -> Dashboard {
        try await perform(path: "/dashboard", queryItems: [URLQueryItem(name: "month", value: month)])
    }

    func listEntries(query: EntryListQuery = EntryListQuery()) async throws -> EntryListResponse {
        try await perform(path: "/entries", queryItems: query.queryItems())
    }

    func runtimeSettings() async throws -> RuntimeSettings {
        try await perform(path: "/settings")
    }

    func listAgentThreads() async throws -> [AgentThreadSummary] {
        try await perform(path: "/agent/threads")
    }

    func createAgentThread(title: String? = nil) async throws -> AgentThread {
        let body = title.map { try? encoder.encode(["title": $0]) } ?? Data("{}".utf8)
        return try await perform(path: "/agent/threads", method: "POST", body: body)
    }

    func agentThread(id: String) async throws -> AgentThreadDetail {
        try await perform(path: "/agent/threads/\(id)")
    }

    func sendAgentMessage(threadId: String, content: String, attachments: [AttachmentUpload]) async throws -> AgentRun {
        let multipart = MultipartFormDataBuilder.agentMessage(content: content, attachments: attachments)
        return try await perform(
            path: "/agent/threads/\(threadId)/messages",
            method: "POST",
            body: multipart.body,
            contentType: multipart.contentType
        )
    }

    func sendAgentMessageStream(
        threadId: String,
        content: String,
        attachments: [AttachmentUpload]
    ) async throws -> HTTPResponseStream {
        let multipart = MultipartFormDataBuilder.agentMessage(content: content, attachments: attachments)
        let request = try makeRequest(
            path: "/agent/threads/\(threadId)/messages/stream",
            method: "POST",
            headers: ["Accept": "text/event-stream"],
            body: multipart.body,
            contentType: multipart.contentType
        )
        let stream = try await transport.stream(for: request)
        guard (200 ..< 300).contains(stream.statusCode) else {
            throw APIError.requestFailed(statusCode: stream.statusCode, message: "Streaming request failed (\(stream.statusCode)).")
        }
        return stream
    }

    func agentRun(id: String) async throws -> AgentRun {
        try await perform(path: "/agent/runs/\(id)")
    }

    func interruptRun(id: String) async throws -> AgentRun {
        try await perform(path: "/agent/runs/\(id)/interrupt", method: "POST", body: Data("{}".utf8))
    }

    func approveChangeItem(
        id: String,
        note: String? = nil,
        payloadOverride: [String: JSONValue]? = nil
    ) async throws -> AgentChangeItem {
        struct RequestBody: Encodable {
            let note: String?
            let payloadOverride: [String: JSONValue]?
        }

        return try await perform(
            path: "/agent/change-items/\(id)/approve",
            method: "POST",
            body: try encoder.encode(RequestBody(note: note, payloadOverride: payloadOverride))
        )
    }

    func rejectChangeItem(id: String, note: String? = nil) async throws -> AgentChangeItem {
        struct RequestBody: Encodable {
            let note: String?
        }

        return try await perform(
            path: "/agent/change-items/\(id)/reject",
            method: "POST",
            body: try encoder.encode(RequestBody(note: note))
        )
    }

    private func perform<Response: Decodable>(
        path: String,
        method: String = "GET",
        queryItems: [URLQueryItem] = [],
        headers: [String: String] = [:],
        body: Data? = nil,
        contentType: String? = "application/json"
    ) async throws -> Response {
        let request = try makeRequest(
            path: path,
            method: method,
            queryItems: queryItems,
            headers: headers,
            body: body,
            contentType: contentType
        )
        let response = try await transport.response(for: request)
        guard (200 ..< 300).contains(response.statusCode) else {
            throw APIError.requestFailed(
                statusCode: response.statusCode,
                message: Self.extractErrorMessage(from: response.data, statusCode: response.statusCode)
            )
        }
        return try decoder.decode(Response.self, from: response.data)
    }

    private func makeRequest(
        path: String,
        method: String,
        queryItems: [URLQueryItem] = [],
        headers: [String: String] = [:],
        body: Data? = nil,
        contentType: String? = nil
    ) throws -> URLRequest {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw APIError.invalidURL(path)
        }

        let normalizedBasePath = baseURL.path.hasSuffix("/") ? String(baseURL.path.dropLast()) : baseURL.path
        let normalizedPath = path.hasPrefix("/") ? path : "/\(path)"
        components.path = normalizedBasePath + normalizedPath
        components.queryItems = queryItems.isEmpty ? nil : queryItems

        guard let url = components.url else {
            throw APIError.invalidURL(path)
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        if let contentType, body != nil {
            request.setValue(contentType, forHTTPHeaderField: "Content-Type")
        }

        if let session = sessionProvider?.currentSession {
            switch session.credential {
            case .principal(let name):
                request.setValue(name, forHTTPHeaderField: "X-Bill-Helper-Principal")
            case .bearerToken(let token):
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
        }

        request.httpBody = body
        return request
    }

    private static func extractErrorMessage(from data: Data, statusCode: Int) -> String {
        guard !data.isEmpty else {
            return "Request failed (\(statusCode))."
        }
        if let payload = try? JSONDecoder().decode(APIDetailPayload.self, from: data),
           let detail = payload.detail,
           !detail.isEmpty {
            return detail
        }
        return String(decoding: data, as: UTF8.self)
    }
}

private struct APIDetailPayload: Decodable {
    let detail: String?
}

extension JSONDecoder {
    static let billHelper: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()
}

extension JSONEncoder {
    static let billHelper: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()
}