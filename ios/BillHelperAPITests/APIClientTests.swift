import XCTest
@testable import BillHelperApp

final class APIClientTests: XCTestCase {
    func testDashboardRequestIncludesPrincipalHeaderAndDecodesSnakeCase() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(
                    data: Data(Self.dashboardPayload.utf8),
                    statusCode: 200,
                    headers: [:]
                )
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let sessionStore = SessionStore(
            storage: InMemorySessionStorage(),
            initialSession: AuthSession(credential: .principal(name: "Alice"), currentUserName: "Alice")
        )
        let client = APIClient(
            baseURL: URL(string: "http://localhost:8000/api/v1")!,
            transport: transport,
            sessionProvider: sessionStore
        )

        let dashboard = try await client.dashboard(month: "2026-03")

        XCTAssertEqual(dashboard.currencyCode, "CAD")
        XCTAssertEqual(dashboard.kpis.expenseTotalMinor, 1200)
        let request = await transport.recordedRequests.first
        XCTAssertEqual(request?.value(forHTTPHeaderField: "X-Bill-Helper-Principal"), "Alice")
        XCTAssertEqual(request?.url?.absoluteString, "http://localhost:8000/api/v1/dashboard?month=2026-03")
    }

    func testDashboardTimelineUsesDedicatedEndpoint() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(
                    data: Data("{\"months\":[\"2026-02\",\"2026-03\"]}".utf8),
                    statusCode: 200,
                    headers: [:]
                )
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        let timeline = try await client.dashboardTimeline()
        let request = await transport.recordedRequests.first

        XCTAssertEqual(timeline.months, ["2026-02", "2026-03"])
        XCTAssertEqual(request?.url?.absoluteString, "http://localhost:8000/api/v1/dashboard/timeline")
    }

    func testListEntriesIncludesQueryParameters() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(data: Data(Self.entriesPayload.utf8), statusCode: 200, headers: [:])
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        _ = try await client.listEntries(
            query: EntryListQuery(kind: .expense, tag: "groceries", limit: 10, offset: 20)
        )

        let request = await transport.recordedRequests.first
        let url = try XCTUnwrap(request?.url)
        let components = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: true))
        let queryItems = components.queryItems ?? []

        XCTAssertEqual(components.path, "/api/v1/entries")
        XCTAssertTrue(queryItems.contains(URLQueryItem(name: "kind", value: "EXPENSE")))
        XCTAssertTrue(queryItems.contains(URLQueryItem(name: "tag", value: "groceries")))
        XCTAssertTrue(queryItems.contains(URLQueryItem(name: "limit", value: "10")))
        XCTAssertTrue(queryItems.contains(URLQueryItem(name: "offset", value: "20")))
    }

    func testUpdateRuntimeSettingsUsesPatchRequest() async throws {
        let request = try await recordRuntimeSettingsUpdateRequest()

        XCTAssertEqual(request.httpMethod, "PATCH")
        XCTAssertEqual(request.url?.path, "/api/v1/settings")
    }

    func testUpdateRuntimeSettingsEncodesCurrencyAndModelFields() async throws {
        let request = try await recordRuntimeSettingsUpdateRequest()
        let json = try Self.jsonBody(from: request)

        XCTAssertEqual(json["default_currency_code"] as? String, "USD")
        XCTAssertEqual(json["dashboard_currency_code"] as? String, "CAD")
        XCTAssertEqual(json["agent_model"] as? String, "gpt-5")
    }

    func testUpdateRuntimeSettingsEncodesAttachmentLimitFields() async throws {
        let request = try await recordRuntimeSettingsUpdateRequest()
        let json = try Self.jsonBody(from: request)

        XCTAssertEqual(json["agent_max_images_per_message"] as? Int, 4)
        XCTAssertEqual(json["agent_max_image_size_bytes"] as? Int, 4_000_000)
    }

    func testCreateAccountEncodesBody() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(data: Data(Self.accountPayload.utf8), statusCode: 200, headers: [:])
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        _ = try await client.createAccount(
            AccountCreatePayload(
                ownerUserId: "user-1",
                name: "Checking",
                markdownBody: "Primary account",
                currencyCode: "CAD"
            )
        )

        let recordedRequest = await transport.recordedRequests.first
        let request = try XCTUnwrap(recordedRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/api/v1/accounts")
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["owner_user_id"] as? String, "user-1")
        XCTAssertEqual(json["name"] as? String, "Checking")
        XCTAssertEqual(json["currency_code"] as? String, "CAD")
        XCTAssertEqual(json["is_active"] as? Bool, true)
    }

    func testAddGroupMemberEncodesChildGroupTarget() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(data: Data(Self.groupGraphPayload.utf8), statusCode: 200, headers: [:])
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        _ = try await client.addGroupMember(
            groupID: "group-1",
            payload: GroupMemberCreatePayload(target: .childGroup(groupId: "group-2"), memberRole: .parent)
        )

        let recordedRequest = await transport.recordedRequests.first
        let request = try XCTUnwrap(recordedRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/api/v1/groups/group-1/members")
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["member_role"] as? String, "PARENT")
        let target = try XCTUnwrap(json["target"] as? [String: Any])
        XCTAssertEqual(target["target_type"] as? String, "child_group")
        XCTAssertEqual(target["group_id"] as? String, "group-2")
    }

    func testRenameAgentThreadUsesPatchRequest() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(data: Data(Self.agentThreadPayload.utf8), statusCode: 200, headers: [:])
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        _ = try await client.renameAgentThread(id: "thread-1", title: "Renamed")

        let recordedRequest = await transport.recordedRequests.first
        let request = try XCTUnwrap(recordedRequest)
        XCTAssertEqual(request.httpMethod, "PATCH")
        XCTAssertEqual(request.url?.path, "/api/v1/agent/threads/thread-1")
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["title"] as? String, "Renamed")
    }

    func testReopenChangeItemPostsOverridePayload() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(data: Data(Self.changeItemPayload.utf8), statusCode: 200, headers: [:])
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        _ = try await client.reopenChangeItem(
            id: "item-1",
            note: "Retry with category",
            payloadOverride: ["category": .string("Meals")]
        )

        let recordedRequest = await transport.recordedRequests.first
        let request = try XCTUnwrap(recordedRequest)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/api/v1/agent/change-items/item-1/reopen")
        let body = try XCTUnwrap(request.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["note"] as? String, "Retry with category")
        let override = try XCTUnwrap(json["payload_override"] as? [String: Any])
        XCTAssertEqual(override["category"] as? String, "Meals")
    }

    func testAgentAttachmentUsesHeadersForMetadata() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(
                    data: Self.jpegHeaderData,
                    statusCode: 200,
                    headers: [
                        "Content-Type": "image/jpeg",
                        "Content-Disposition": "attachment; filename=\"receipt.jpg\"",
                    ]
                )
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        let resource = try await client.agentAttachment(id: "attachment-1")

        XCTAssertEqual(resource.mimeType, "image/jpeg")
        XCTAssertEqual(resource.fileName, "receipt.jpg")
        XCTAssertEqual(resource.data, Self.jpegHeaderData)
    }

    func testAgentAttachmentSanitizesUnsafeHeaderFilename() async throws {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(
                    data: Self.jpegHeaderData,
                    statusCode: 200,
                    headers: [
                        "Content-Type": "image/jpeg",
                        "Content-Disposition": "attachment; filename=\"../../receipt.jpg\"",
                    ]
                )
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        let resource = try await client.agentAttachment(id: "attachment-1")

        XCTAssertEqual(resource.fileName, "receipt.jpg")
    }

    private func recordRuntimeSettingsUpdateRequest() async throws -> URLRequest {
        let transport = MockHTTPTransport(
            responseHandler: { _ in
                HTTPResponse(data: Data(Self.runtimeSettingsPayload.utf8), statusCode: 200, headers: [:])
            },
            streamHandler: { _ in
                HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
            }
        )
        let client = APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)

        _ = try await client.updateRuntimeSettings(Self.runtimeSettingsUpdatePayload)

        let recordedRequest = await transport.recordedRequests.first
        return try XCTUnwrap(recordedRequest)
    }

    private static func jsonBody(from request: URLRequest) throws -> [String: Any] {
        let body = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
    }

    private static let dashboardPayload = """
    {
      "month": "2026-03",
      "currency_code": "CAD",
      "kpis": {
        "expense_total_minor": 1200,
        "income_total_minor": 4000,
        "net_total_minor": 2800,
        "average_expense_day_minor": 100,
        "median_expense_day_minor": 90,
        "spending_days": 8
      },
      "filter_groups": [],
      "daily_spending": [],
      "monthly_trend": [],
      "spending_by_from": [],
      "spending_by_to": [],
      "spending_by_tag": [],
      "weekday_spending": [],
      "largest_expenses": [],
      "projection": {
        "is_current_month": true,
        "days_elapsed": 8,
        "days_remaining": 23,
        "spent_to_date_minor": 1200,
        "projected_total_minor": 4650,
        "projected_remaining_minor": 3450,
        "projected_filter_group_totals": {}
      },
      "reconciliation": []
    }
    """

    private static let entriesPayload = """
    {
      "items": [],
      "total": 0,
      "limit": 10,
      "offset": 20
    }
    """

    private static let runtimeSettingsPayload = """
    {
      "current_user_name": "Casey",
      "user_memory": ["Track dining"],
      "default_currency_code": "CAD",
      "dashboard_currency_code": "CAD",
      "agent_model": "gpt-5",
      "available_agent_models": ["gpt-5", "gpt-5-mini"],
      "agent_max_steps": 12,
      "agent_bulk_max_concurrent_threads": 3,
      "agent_retry_max_attempts": 4,
      "agent_retry_initial_wait_seconds": 1.5,
      "agent_retry_max_wait_seconds": 20,
      "agent_retry_backoff_multiplier": 2,
      "agent_max_image_size_bytes": 4000000,
      "agent_max_images_per_message": 4,
      "agent_base_url": "https://openrouter.ai/api/v1",
      "agent_api_key_configured": true,
      "overrides": {
        "user_memory": ["Track dining"],
        "default_currency_code": "CAD",
        "dashboard_currency_code": "CAD",
        "agent_model": "gpt-5",
        "available_agent_models": ["gpt-5", "gpt-5-mini"],
        "agent_max_steps": 12,
        "agent_bulk_max_concurrent_threads": 3,
        "agent_retry_max_attempts": 4,
        "agent_retry_initial_wait_seconds": 1.5,
        "agent_retry_max_wait_seconds": 20,
        "agent_retry_backoff_multiplier": 2,
        "agent_max_image_size_bytes": 4000000,
        "agent_max_images_per_message": 4,
        "agent_base_url": "https://openrouter.ai/api/v1",
        "agent_api_key_configured": true
      }
    }
    """

    private static let runtimeSettingsUpdatePayload = RuntimeSettingsUpdatePayload(
        userMemory: ["Track dining"],
        defaultCurrencyCode: "USD",
        dashboardCurrencyCode: "CAD",
        agentModel: "gpt-5",
        availableAgentModels: ["gpt-5", "gpt-5-mini"],
        agentMaxSteps: 12,
        agentBulkMaxConcurrentThreads: 3,
        agentRetryMaxAttempts: 4,
        agentRetryInitialWaitSeconds: 1.5,
        agentRetryMaxWaitSeconds: 20,
        agentRetryBackoffMultiplier: 2,
        agentMaxImageSizeBytes: 4_000_000,
        agentMaxImagesPerMessage: 4,
        agentBaseURL: "https://openrouter.ai/api/v1",
        agentApiKey: "secret"
    )

    private static let jpegHeaderData = Data([0xFF, 0xD8, 0xFF])

    private static let accountPayload = """
    {
      "id": "account-1",
      "owner_user_id": "user-1",
      "name": "Checking",
      "markdown_body": "Primary account",
      "currency_code": "CAD",
      "is_active": true,
      "created_at": "2026-03-01T00:00:00Z",
      "updated_at": "2026-03-01T00:00:00Z"
    }
    """

    private static let groupGraphPayload = """
    {
      "id": "group-1",
      "name": "Trip split",
      "group_type": "SPLIT",
      "parent_group_id": null,
      "direct_member_count": 1,
      "direct_entry_count": 0,
      "direct_child_group_count": 1,
      "descendant_entry_count": 0,
      "first_occurred_at": null,
      "last_occurred_at": null,
      "nodes": [],
      "edges": []
    }
    """

    private static let agentThreadPayload = """
    {
      "id": "thread-1",
      "title": "Renamed",
      "created_at": "2026-03-01T00:00:00Z",
      "updated_at": "2026-03-02T00:00:00Z"
    }
    """

    private static let changeItemPayload = """
    {
      "id": "item-1",
      "run_id": "run-1",
      "change_type": "create_entry",
      "payload_json": {"category": "Meals"},
      "rationale_text": "Retrying with override",
      "status": "PENDING_REVIEW",
      "review_note": null,
      "applied_resource_type": null,
      "applied_resource_id": null,
      "created_at": "2026-03-01T00:00:00Z",
      "updated_at": "2026-03-01T00:00:00Z",
      "review_actions": []
    }
    """
}

private actor MockHTTPTransport: HTTPTransport {
    private(set) var recordedRequests: [URLRequest] = []
    private let responseHandler: @Sendable (URLRequest) throws -> HTTPResponse
    private let streamHandler: @Sendable (URLRequest) throws -> HTTPResponseStream

    init(
        responseHandler: @escaping @Sendable (URLRequest) throws -> HTTPResponse,
        streamHandler: @escaping @Sendable (URLRequest) throws -> HTTPResponseStream
    ) {
        self.responseHandler = responseHandler
        self.streamHandler = streamHandler
    }

    func response(for request: URLRequest) async throws -> HTTPResponse {
        recordedRequests.append(request)
        return try responseHandler(request)
    }

    func stream(for request: URLRequest) async throws -> HTTPResponseStream {
        recordedRequests.append(request)
        return try streamHandler(request)
    }
}
