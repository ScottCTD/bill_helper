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
        let url = try XCTUnwrap(request?.url?.absoluteString)
        XCTAssertTrue(url.contains("kind=EXPENSE"))
        XCTAssertTrue(url.contains("tag=groceries"))
        XCTAssertTrue(url.contains("limit=10"))
        XCTAssertTrue(url.contains("offset=20"))
    }

    private static let dashboardPayload = """
    {
      "month": "2026-03",
      "currency_code": "CAD",
      "kpis": {
        "expense_total_minor": 1200,
        "income_total_minor": 4000,
        "net_total_minor": 2800,
        "daily_expense_total_minor": 800,
        "non_daily_expense_total_minor": 400,
        "average_daily_expense_minor": 100,
        "median_daily_expense_minor": 90,
        "daily_spending_days": 8
      },
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
        "projected_remaining_minor": 3450
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