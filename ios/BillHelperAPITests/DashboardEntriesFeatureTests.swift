import XCTest
@testable import BillHelperApp

@MainActor
final class DashboardEntriesFeatureTests: XCTestCase {
    func testDashboardModelLoadsTimelineAndDashboard() async throws {
        let dashboard = Self.sampleDashboard(expenseTotalMinor: 125_00, largestExpenses: [Self.sampleLargestExpense])
        let client = makeClient(
            responses: [
                "/dashboard/timeline": try Self.encode(DashboardTimeline(months: ["2026-02", "2026-03"])),
                "/dashboard": try Self.encode(dashboard),
            ]
        )
        let model = DashboardScreenModel(apiClient: client)
        model.selectedMonth = "2026-03"

        await model.loadIfNeeded()

        XCTAssertEqual(model.timelineMonths, ["2026-02", "2026-03"])
        XCTAssertEqual(model.phase, .loaded(dashboard))
        XCTAssertEqual(model.selectedFilterGroupKey, "groceries")
    }

    func testDashboardModelMarksZeroedDashboardAsEmpty() async throws {
        let dashboard = Self.sampleDashboard(expenseTotalMinor: 0, largestExpenses: [])
        let client = makeClient(
            responses: [
                "/dashboard/timeline": try Self.encode(DashboardTimeline(months: ["2026-03"])),
                "/dashboard": try Self.encode(dashboard),
            ]
        )
        let model = DashboardScreenModel(apiClient: client)

        await model.reload()

        XCTAssertEqual(model.phase, .empty(dashboard))
    }

    func testDashboardModelFallsBackToLatestAvailableMonthAndFilterGroup() async throws {
        let dashboard = Self.sampleDashboard(expenseTotalMinor: 125_00, largestExpenses: [Self.sampleLargestExpense])
        let client = makeClient(
            responses: [
                "/dashboard/timeline": try Self.encode(DashboardTimeline(months: ["2026-02", "2026-03"])),
                "/dashboard": try Self.encode(dashboard),
            ]
        )
        let model = DashboardScreenModel(apiClient: client)
        model.selectedMonth = "2026-04"
        model.selectedFilterGroupKey = "legacy-group"

        await model.reload()

        XCTAssertEqual(model.selectedMonth, "2026-03")
        XCTAssertEqual(model.selectedFilterGroupKey, "groceries")
        XCTAssertEqual(model.phase, .loaded(dashboard))
    }

    func testEntriesModelLoadsItemsAndSupportingData() async throws {
        let response = EntryListResponse(items: [Self.sampleEntry], total: 1, limit: 50, offset: 0)
        let client = makeClient(
            responses: [
                "/entries": try Self.encode(response),
                "/tags": try Self.encode([Self.sampleTag]),
                "/groups": try Self.encode([Self.sampleGroup]),
                "/entities": try Self.encode([Self.sampleEntity]),
                "/users": try Self.encode([Self.sampleUser]),
                "/currencies": try Self.encode([Self.sampleCurrency]),
                "/filter-groups": try Self.encode([Self.sampleFilterGroup]),
            ]
        )
        let model = EntriesScreenModel(apiClient: client)

        await model.loadIfNeeded()

        XCTAssertEqual(model.phase, .loaded(response))
        XCTAssertEqual(model.tags, [Self.sampleTag])
        XCTAssertEqual(model.groups, [Self.sampleGroup])
        XCTAssertEqual(model.entities, [Self.sampleEntity])
        XCTAssertEqual(model.users, [Self.sampleUser])
        XCTAssertEqual(model.currencies, [Self.sampleCurrency])
        XCTAssertEqual(model.filterGroups, [Self.sampleFilterGroup])
    }

    func testEntriesModelSurfacesErrorMessage() async {
        let client = makeClient(
            responseHandler: { request in
                guard request.url?.path == "/api/v1/entries" else {
                    return HTTPResponse(data: Data("[]".utf8), statusCode: 200, headers: [:])
                }
                return HTTPResponse(data: Data("{\"detail\":\"Server unavailable\"}".utf8), statusCode: 503, headers: [:])
            }
        )
        let model = EntriesScreenModel(apiClient: client)

        await model.reload()

        XCTAssertEqual(model.phase, .failed("Server unavailable"))
    }

    func testDashboardMonthPickerStateUsesSelectedMonthWhenTimelineIsEmpty() {
        XCTAssertEqual(
            DashboardMonthPickerState.availableMonths(timelineMonths: [], selectedMonth: "2026-03"),
            ["2026-03"]
        )
        XCTAssertEqual(
            DashboardMonthPickerState.availableMonths(timelineMonths: ["2026-02", "2026-03"], selectedMonth: "2026-03"),
            ["2026-02", "2026-03"]
        )
    }

    func testEntryTagSelectionNormalizesAndDeduplicatesValues() {
        XCTAssertEqual(
            EntryTagSelection.normalize([" Groceries ", "groceries", "TRAVEL", "", "travel "]),
            ["groceries", "travel"]
        )
    }

    func testEntryTagSelectionToggleAndRemoveAreStable() {
        let toggled = EntryTagSelection.toggle("Groceries", in: ["travel"])
        XCTAssertEqual(toggled, ["travel", "groceries"])
        XCTAssertEqual(EntryTagSelection.toggle("travel", in: toggled), ["groceries"])
        XCTAssertEqual(EntryTagSelection.remove("groceries", from: toggled), ["travel"])
    }

    func testEntryTagSelectionFilteredOptionsIncludeSelectedCustomTags() {
        let options = EntryTagSelection.filteredOptions(
            tags: [Self.sampleTag],
            selected: ["travel", "groceries"],
            query: "tr"
        )

        XCTAssertEqual(options, [EntryDisplayedTag(key: "travel", name: "travel", color: nil)])
    }

    func testEntryTagSelectionCreatableTagOnlyAppearsForUnknownValue() {
        XCTAssertEqual(
            EntryTagSelection.creatableTagName(
                tags: [Self.sampleTag],
                selected: ["travel"],
                query: " dining ",
                allowCreate: true
            ),
            "dining"
        )
        XCTAssertNil(
            EntryTagSelection.creatableTagName(
                tags: [Self.sampleTag],
                selected: ["travel"],
                query: "groceries",
                allowCreate: true
            )
        )
        XCTAssertNil(
            EntryTagSelection.creatableTagName(
                tags: [Self.sampleTag],
                selected: ["travel"],
                query: "travel",
                allowCreate: true
            )
        )
    }

    private func makeClient(
        responses: [String: Data] = [:],
        responseHandler: (@Sendable (URLRequest) throws -> HTTPResponse)? = nil
    ) -> APIClient {
        let transport = DashboardEntriesMockTransport(
            responseHandler: responseHandler ?? { request in
                let path = request.url?.path.replacingOccurrences(of: "/api/v1", with: "") ?? ""
                guard let data = responses[path] else {
                    return HTTPResponse(data: Data("{}".utf8), statusCode: 404, headers: [:])
                }
                return HTTPResponse(data: data, statusCode: 200, headers: [:])
            }
        )
        return APIClient(baseURL: URL(string: "http://localhost:8000/api/v1")!, transport: transport)
    }

    private static func encode<T: Encodable>(_ value: T) throws -> Data {
        try JSONEncoder.billHelper.encode(value)
    }

    private static let sampleLargestExpense = DashboardLargestExpenseItem(
        id: "expense-1",
        occurredAt: "2026-03-08",
        name: "Groceries",
        toEntity: "Fresh Market",
        amountMinor: 72_45,
        matchingFilterGroupKeys: ["groceries"]
    )

    private static let sampleTag = Tag(
        id: 1,
        name: "groceries",
        color: nil,
        description: nil,
        type: nil,
        entryCount: 1
    )

    private static let sampleGroup = GroupSummary(
        id: "group-1",
        name: "March split",
        groupType: .split,
        parentGroupId: nil,
        directMemberCount: 1,
        directEntryCount: 1,
        directChildGroupCount: 0,
        descendantEntryCount: 1,
        firstOccurredAt: "2026-03-07",
        lastOccurredAt: "2026-03-07"
    )

    private static let sampleEntity = Entity(
        id: "entity-1",
        name: "Fresh Market",
        category: "merchant",
        isAccount: false,
        fromCount: nil,
        toCount: 1,
        accountCount: nil,
        entryCount: 1,
        netAmountMinor: 72_45,
        netAmountCurrencyCode: "CAD",
        netAmountMixedCurrencies: false
    )

    private static let sampleUser = User(
        id: "user-1",
        name: "Casey",
        isAdmin: true,
        isCurrentUser: true,
        accountCount: 1,
        entryCount: 1
    )

    private static let sampleCurrency = Currency(
        code: "CAD",
        name: "Canadian Dollar",
        entryCount: 1,
        isPlaceholder: false
    )

    private static let sampleFilterGroup = FilterGroup(
        id: "filter-1",
        key: "groceries",
        name: "Groceries",
        description: nil,
        color: "#44AA55",
        isDefault: true,
        position: 0,
        rule: FilterGroupRule(
            include: FilterRuleGroup(
                operator: .and,
                children: [.condition(FilterRuleCondition(field: .tags, operator: .hasAny, value: .strings(["groceries"])))]
            ),
            exclude: nil
        ),
        ruleSummary: "Includes grocery tags",
        createdAt: "2026-03-01T00:00:00Z",
        updatedAt: "2026-03-01T00:00:00Z"
    )

    private static let sampleEntry = Entry(
        id: "entry-1",
        accountId: nil,
        kind: .expense,
        occurredAt: "2026-03-07",
        name: "Groceries",
        amountMinor: 72_45,
        currencyCode: "CAD",
        fromEntityId: nil,
        toEntityId: nil,
        ownerUserId: nil,
        fromEntity: "Checking",
        fromEntityMissing: false,
        toEntity: "Fresh Market",
        toEntityMissing: false,
        owner: "Casey",
        markdownBody: "Weekly groceries.",
        createdAt: "2026-03-07T15:00:00Z",
        updatedAt: "2026-03-07T15:00:00Z",
        tags: [sampleTag],
        directGroup: nil,
        directGroupMemberRole: nil,
        groupPath: []
    )

    private static func sampleDashboard(
        expenseTotalMinor: Int,
        largestExpenses: [DashboardLargestExpenseItem]
    ) -> Dashboard {
        let hasContent = expenseTotalMinor != 0 || !largestExpenses.isEmpty

        return Dashboard(
            month: "2026-03",
            currencyCode: "CAD",
            kpis: DashboardKpis(
                expenseTotalMinor: expenseTotalMinor,
                incomeTotalMinor: hasContent ? 400_00 : 0,
                netTotalMinor: hasContent ? 275_00 : 0,
                averageExpenseDayMinor: expenseTotalMinor,
                medianExpenseDayMinor: expenseTotalMinor,
                spendingDays: expenseTotalMinor == 0 ? 0 : 1
            ),
            filterGroups: hasContent ? [
                DashboardFilterGroupSummary(
                    filterGroupId: "filter-1",
                    key: "groceries",
                    name: "Groceries",
                    color: "#44AA55",
                    totalMinor: expenseTotalMinor,
                    share: 1
                )
            ] : [],
            dailySpending: [],
            monthlyTrend: [],
            spendingByFrom: [],
            spendingByTo: hasContent ? [DashboardBreakdownItem(label: "Fresh Market", totalMinor: expenseTotalMinor, share: 1)] : [],
            spendingByTag: [],
            weekdaySpending: [],
            largestExpenses: largestExpenses,
            projection: DashboardProjection(
                isCurrentMonth: true,
                daysElapsed: 8,
                daysRemaining: 23,
                spentToDateMinor: expenseTotalMinor,
                projectedTotalMinor: hasContent ? 320_00 : nil,
                projectedRemainingMinor: hasContent ? 195_00 : nil,
                projectedFilterGroupTotals: hasContent ? ["groceries": expenseTotalMinor] : [:]
            ),
            reconciliation: []
        )
    }
}

private actor DashboardEntriesMockTransport: HTTPTransport {
    private let responseHandler: @Sendable (URLRequest) throws -> HTTPResponse

    init(responseHandler: @escaping @Sendable (URLRequest) throws -> HTTPResponse) {
        self.responseHandler = responseHandler
    }

    func response(for request: URLRequest) async throws -> HTTPResponse {
        try responseHandler(request)
    }

    func stream(for request: URLRequest) async throws -> HTTPResponseStream {
        HTTPResponseStream(statusCode: 200, headers: [:], chunks: AsyncThrowingStream { $0.finish() })
    }
}
