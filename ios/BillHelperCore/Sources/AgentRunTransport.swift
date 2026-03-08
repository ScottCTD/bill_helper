import Foundation

enum AgentRunUpdate: Equatable, Sendable {
    case snapshot(AgentRun)
    case event(AgentStreamEvent)
}

enum AgentRunUpdateStrategy: Equatable, Sendable {
    case serverEvents
    case polling(interval: Duration)
    case automatic(pollInterval: Duration)
}

struct AgentRunTransport: @unchecked Sendable {
    let apiClient: APIClient
    let strategy: AgentRunUpdateStrategy

    init(apiClient: APIClient, strategy: AgentRunUpdateStrategy = .automatic(pollInterval: .seconds(1))) {
        self.apiClient = apiClient
        self.strategy = strategy
    }

    func startMessageRun(
        threadId: String,
        content: String,
        attachments: [AttachmentUpload]
    ) -> AsyncThrowingStream<AgentRunUpdate, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    try await produceUpdates(
                        threadId: threadId,
                        content: content,
                        attachments: attachments,
                        continuation: continuation
                    )
                    continuation.finish()
                } catch is CancellationError {
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }

    private func produceUpdates(
        threadId: String,
        content: String,
        attachments: [AttachmentUpload],
        continuation: AsyncThrowingStream<AgentRunUpdate, Error>.Continuation
    ) async throws {
        switch strategy {
        case .serverEvents:
            try await streamMessageRun(threadId: threadId, content: content, attachments: attachments, continuation: continuation)
        case .polling(let interval):
            try await sendAndPoll(threadId: threadId, content: content, attachments: attachments, interval: interval, continuation: continuation)
        case .automatic(let pollInterval):
            do {
                try await streamMessageRun(threadId: threadId, content: content, attachments: attachments, continuation: continuation)
            } catch let error as StreamProgressError {
                if let runId = error.emittedRunId {
                    try await pollExistingRun(runId: runId, interval: pollInterval, continuation: continuation)
                } else if !error.emittedAnyEvent {
                    try await sendAndPoll(
                        threadId: threadId,
                        content: content,
                        attachments: attachments,
                        interval: pollInterval,
                        continuation: continuation
                    )
                } else {
                    throw error.underlying
                }
            }
        }
    }

    private func streamMessageRun(
        threadId: String,
        content: String,
        attachments: [AttachmentUpload],
        continuation: AsyncThrowingStream<AgentRunUpdate, Error>.Continuation
    ) async throws {
        var parser = AgentSSEEventParser()
        var latestRunId: String?
        var emittedAnyEvent = false

        do {
            let stream = try await apiClient.sendAgentMessageStream(threadId: threadId, content: content, attachments: attachments)
            for try await chunk in stream.chunks {
                try Task.checkCancellation()
                for event in try parser.consume(chunk) {
                    latestRunId = latestRunId ?? event.runId
                    emittedAnyEvent = true
                    continuation.yield(.event(event))
                }
            }
            for event in try parser.finish() {
                latestRunId = latestRunId ?? event.runId
                emittedAnyEvent = true
                continuation.yield(.event(event))
            }
        } catch {
            throw StreamProgressError(underlying: error, emittedRunId: latestRunId, emittedAnyEvent: emittedAnyEvent)
        }

        if let latestRunId {
            continuation.yield(.snapshot(try await apiClient.agentRun(id: latestRunId)))
        }
    }

    private func sendAndPoll(
        threadId: String,
        content: String,
        attachments: [AttachmentUpload],
        interval: Duration,
        continuation: AsyncThrowingStream<AgentRunUpdate, Error>.Continuation
    ) async throws {
        let initialRun = try await apiClient.sendAgentMessage(threadId: threadId, content: content, attachments: attachments)
        try await pollExistingRun(runId: initialRun.id, seed: initialRun, interval: interval, continuation: continuation)
    }

    private func pollExistingRun(
        runId: String,
        seed: AgentRun? = nil,
        interval: Duration,
        continuation: AsyncThrowingStream<AgentRunUpdate, Error>.Continuation
    ) async throws {
        var current: AgentRun
        if let seed {
            current = seed
        } else {
            current = try await apiClient.agentRun(id: runId)
        }
        continuation.yield(.snapshot(current))
        while !current.status.isTerminal {
            try await Task.sleep(for: interval)
            let updated = try await apiClient.agentRun(id: runId)
            if updated != current {
                continuation.yield(.snapshot(updated))
                current = updated
            }
        }
    }
}

struct AgentSSEEventParser {
    private var buffer = ""

    mutating func consume(_ data: Data) throws -> [AgentStreamEvent] {
        guard !data.isEmpty else {
            return []
        }
        buffer += String(decoding: data, as: UTF8.self).replacingOccurrences(of: "\r", with: "")
        return try drainCompleteBlocks()
    }

    mutating func finish() throws -> [AgentStreamEvent] {
        defer { buffer = "" }
        let remainder = buffer.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !remainder.isEmpty else {
            return []
        }
        return try decode(block: remainder).map { [$0] } ?? []
    }

    private mutating func drainCompleteBlocks() throws -> [AgentStreamEvent] {
        var events: [AgentStreamEvent] = []
        while let separatorRange = buffer.range(of: "\n\n") {
            let block = String(buffer[..<separatorRange.lowerBound])
            buffer.removeSubrange(buffer.startIndex..<separatorRange.upperBound)
            if let event = try decode(block: block) {
                events.append(event)
            }
        }
        return events
    }

    private func decode(block: String) throws -> AgentStreamEvent? {
        var dataLines: [String] = []
        for rawLine in block.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(rawLine)
            if line.isEmpty || line.hasPrefix(":") || line.hasPrefix("event:") {
                continue
            }
            if line.hasPrefix("data:") {
                let remainder = line.dropFirst(5)
                dataLines.append(String(remainder).trimmingLeadingWhitespace())
            }
        }
        guard !dataLines.isEmpty else {
            return nil
        }
        return try JSONDecoder.billHelper.decode(AgentStreamEvent.self, from: Data(dataLines.joined(separator: "\n").utf8))
    }
}

private struct StreamProgressError: Error {
    let underlying: Error
    let emittedRunId: String?
    let emittedAnyEvent: Bool
}

private extension String {
    func trimmingLeadingWhitespace() -> String {
        String(trimmingPrefix(while: \.isWhitespace))
    }
}