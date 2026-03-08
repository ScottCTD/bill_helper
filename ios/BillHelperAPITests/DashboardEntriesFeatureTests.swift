import XCTest
@testable import BillHelperApp

@MainActor
final class DashboardEntriesFeatureTests: XCTestCase {
    func testDashboardModelLoadsNonEmptyDashboard() async {
        let dashboard = Self.sampleDashboard(expenseTotalMinor: 125_00, largestExpenses: [Self.sampleLargestExpense])
        let model = DashboardScreenModel(month: "2026-03") { _ in dashboard }

        await model.loadIfNeeded()

        XCTAssertEqual(model.phase, .loaded(dashboard))
    }

    func testDashboardModelMarksZeroedDashboardAsEmpty() async {
        let dashboard = Self.sampleDashboard(expenseTotalMinor: 0, largestExpenses: [])
        let model = DashboardScreenModel(month: "2026-03") { _ in dashboard }

        await model.reload()

        XCTAssertEqual(model.phase, .empty(dashboard))
    }

    func testEntriesModelLoadsItems() async {
        let response = EntryListResponse(items: [Self.sampleEntry], total: 1, limit: 50, offset: 0)
        let model = EntriesScreenModel { response }

        await model.loadIfNeeded()

        XCTAssertEqual(model.phase, .loaded(response))
    }

    func testEntriesModelSurfacesErrorMessage() async {
        struct SampleError: LocalizedError {
            var errorDescription: String? { "Server unavailable" }
        }

        let model = EntriesScreenModel {
            throw SampleError()
        }

        await model.reload()

        XCTAssertEqual(model.phase, .failed("Server unavailable"))
    }

    private static let sampleLargestExpense = DashboardLargestExpenseItem(
        id: "expense-1",
        occurredAt: "2026-03-08",
        name: "Groceries",
        toEntity: "Fresh Market",
        amountMinor: 72_45,
        isDaily: false
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
        tags: [Tag(id: 1, name: "groceries", color: nil, description: nil, type: nil, entryCount: nil)],
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
                dailyExpenseTotalMinor: expenseTotalMinor,
                nonDailyExpenseTotalMinor: 0,
                averageDailyExpenseMinor: expenseTotalMinor,
                medianDailyExpenseMinor: expenseTotalMinor,
                dailySpendingDays: expenseTotalMinor == 0 ? 0 : 1
            ),
            dailySpending: [],
            monthlyTrend: [],
            spendingByFrom: [],
            spendingByTo: hasContent ? [DashboardBreakdownItem(label: "Fresh Market", totalMinor: expenseTotalMinor, share: 1.0)] : [],
            spendingByTag: [],
            weekdaySpending: [],
            largestExpenses: largestExpenses,
            projection: DashboardProjection(
                isCurrentMonth: true,
                daysElapsed: 8,
                daysRemaining: 23,
                spentToDateMinor: expenseTotalMinor,
                projectedTotalMinor: hasContent ? 320_00 : nil,
                projectedRemainingMinor: hasContent ? 195_00 : nil
            ),
            reconciliation: []
        )
    }
}