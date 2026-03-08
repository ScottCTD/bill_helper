import XCTest
@testable import BillHelperApp

final class AgentRunTransportTests: XCTestCase {
    func testAutomaticStrategyFallsBackToPollingWhenStreamSetupFails() async throws {
        let transport = PollingFallbackTransport()
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)
        let runTransport = AgentRunTransport(apiClient: client, strategy: .automatic(pollInterval: .milliseconds(1)))

        var snapshots: [AgentRun] = []
        for try await update in runTransport.startMessageRun(threadId: "thread-1", content: "Review this.", attachments: []) {
            if case .snapshot(let run) = update {
                snapshots.append(run)
                if run.status.isTerminal {
                    break
                }
            }
        }

        XCTAssertEqual(snapshots.map(\.status), [.running, .completed])
        let paths = await transport.recordedPaths()
        XCTAssertEqual(paths, [
            "/api/v1/agent/threads/thread-1/messages/stream",
            "/api/v1/agent/threads/thread-1/messages",
            "/api/v1/agent/runs/run-1",
        ])
    }

    func testSSEParserDecodesChunkedEvents() throws {
        var parser = AgentSSEEventParser()
        let firstChunk = Data("event: reasoning_delta\ndata: {\"type\":\"reasoning_delta\",\"run_id\":\"run-1\",\"delta\":\"Thinking".utf8)
        let secondChunk = Data("...\"}\n\n".utf8)

        XCTAssertTrue(try parser.consume(firstChunk).isEmpty)
        let events = try parser.consume(secondChunk)

        XCTAssertEqual(events, [.reasoningDelta(runId: "run-1", delta: "Thinking...")])
    }
}

private actor PollingFallbackTransport: HTTPTransport {
    private var requests: [String] = []

    func response(for request: URLRequest) async throws -> HTTPResponse {
        requests.append(request.url?.path ?? "")
        switch request.url?.path {
        case "/api/v1/agent/threads/thread-1/messages":
            return HTTPResponse(data: Data(Self.runningRunPayload.utf8), statusCode: 200, headers: [:])
        case "/api/v1/agent/runs/run-1":
            return HTTPResponse(data: Data(Self.completedRunPayload.utf8), statusCode: 200, headers: [:])
        default:
            return HTTPResponse(data: Data(), statusCode: 404, headers: [:])
        }
    }

    func stream(for request: URLRequest) async throws -> HTTPResponseStream {
        requests.append(request.url?.path ?? "")
        throw URLError(.networkConnectionLost)
    }

    func recordedPaths() -> [String] {
        requests
    }

    private static let runningRunPayload = """
    {
      "id": "run-1",
      "thread_id": "thread-1",
      "user_message_id": "message-1",
      "assistant_message_id": null,
      "status": "running",
      "model_name": "gpt-5",
      "context_tokens": null,
      "input_tokens": null,
      "output_tokens": null,
      "cache_read_tokens": null,
      "cache_write_tokens": null,
      "input_cost_usd": null,
      "output_cost_usd": null,
      "total_cost_usd": null,
      "error_text": null,
      "created_at": "2026-03-08T00:00:00Z",
      "completed_at": null,
      "events": [],
      "tool_calls": [],
      "change_items": []
    }
    """

    private static let completedRunPayload = """
    {
      "id": "run-1",
      "thread_id": "thread-1",
      "user_message_id": "message-1",
      "assistant_message_id": "message-2",
      "status": "completed",
      "model_name": "gpt-5",
      "context_tokens": 10,
      "input_tokens": 20,
      "output_tokens": 30,
      "cache_read_tokens": null,
      "cache_write_tokens": null,
      "input_cost_usd": null,
      "output_cost_usd": null,
      "total_cost_usd": null,
      "error_text": null,
      "created_at": "2026-03-08T00:00:00Z",
      "completed_at": "2026-03-08T00:00:03Z",
      "events": [],
      "tool_calls": [],
      "change_items": []
    }
    """
}