import Foundation

struct DashboardKpis: Codable, Equatable, Hashable, Sendable {
    let expenseTotalMinor: Int
    let incomeTotalMinor: Int
    let netTotalMinor: Int
    let averageExpenseDayMinor: Int
    let medianExpenseDayMinor: Int
    let spendingDays: Int
}

struct DashboardFilterGroupSummary: Codable, Equatable, Hashable, Sendable {
    let filterGroupId: String
    let key: String
    let name: String
    let color: String?
    let totalMinor: Int
    let share: Double
}

struct DashboardDailySpendingPoint: Codable, Equatable, Hashable, Sendable {
    let date: String
    let expenseTotalMinor: Int
    let filterGroupTotals: [String: Int]
}

struct DashboardMonthlyTrendPoint: Codable, Equatable, Hashable, Sendable {
    let month: String
    let expenseTotalMinor: Int
    let incomeTotalMinor: Int
    let filterGroupTotals: [String: Int]
}

struct DashboardBreakdownItem: Codable, Equatable, Hashable, Sendable {
    let label: String
    let totalMinor: Int
    let share: Double
}

struct DashboardWeekdaySpendingPoint: Codable, Equatable, Hashable, Sendable {
    let weekday: String
    let totalMinor: Int
}

struct DashboardLargestExpenseItem: Codable, Equatable, Hashable, Sendable {
    let id: String
    let occurredAt: String
    let name: String
    let toEntity: String?
    let amountMinor: Int
    let matchingFilterGroupKeys: [String]
}

struct DashboardProjection: Codable, Equatable, Hashable, Sendable {
    let isCurrentMonth: Bool
    let daysElapsed: Int
    let daysRemaining: Int
    let spentToDateMinor: Int
    let projectedTotalMinor: Int?
    let projectedRemainingMinor: Int?
    let projectedFilterGroupTotals: [String: Int]
}

struct DashboardTimeline: Codable, Equatable, Hashable, Sendable {
    let months: [String]
}

struct DashboardReconciliation: Codable, Equatable, Hashable, Sendable {
    let accountId: String
    let accountName: String
    let currencyCode: String
    let latestSnapshotAt: String?
    let currentTrackedChangeMinor: Int?
    let lastClosedDeltaMinor: Int?
    let mismatchedIntervalCount: Int
    let reconciledIntervalCount: Int
}

struct Dashboard: Codable, Equatable, Sendable {
    let month: String
    let currencyCode: String
    let kpis: DashboardKpis
    let filterGroups: [DashboardFilterGroupSummary]
    let dailySpending: [DashboardDailySpendingPoint]
    let monthlyTrend: [DashboardMonthlyTrendPoint]
    let spendingByFrom: [DashboardBreakdownItem]
    let spendingByTo: [DashboardBreakdownItem]
    let spendingByTag: [DashboardBreakdownItem]
    let weekdaySpending: [DashboardWeekdaySpendingPoint]
    let largestExpenses: [DashboardLargestExpenseItem]
    let projection: DashboardProjection
    let reconciliation: [DashboardReconciliation]
}
