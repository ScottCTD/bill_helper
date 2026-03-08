import Foundation

enum EntryKind: String, Codable, Equatable {
    case expense = "EXPENSE"
    case income = "INCOME"
    case transfer = "TRANSFER"
}

enum GroupType: String, Codable, Equatable {
    case bundle = "BUNDLE"
    case split = "SPLIT"
    case recurring = "RECURRING"
}

enum GroupMemberRole: String, Codable, Equatable {
    case parent = "PARENT"
    case child = "CHILD"
}

struct Tag: Codable, Equatable {
    let id: Int
    let name: String
    let color: String?
    let description: String?
    let type: String?
    let entryCount: Int?
}

struct EntryGroupRef: Codable, Equatable {
    let id: String
    let name: String
    let groupType: GroupType
}

struct Entry: Codable, Equatable {
    let id: String
    let accountId: String?
    let kind: EntryKind
    let occurredAt: String
    let name: String
    let amountMinor: Int
    let currencyCode: String
    let fromEntityId: String?
    let toEntityId: String?
    let ownerUserId: String?
    let fromEntity: String?
    let fromEntityMissing: Bool
    let toEntity: String?
    let toEntityMissing: Bool
    let owner: String?
    let markdownBody: String?
    let createdAt: String
    let updatedAt: String
    let tags: [Tag]
    let directGroup: EntryGroupRef?
    let directGroupMemberRole: GroupMemberRole?
    let groupPath: [EntryGroupRef]
}

struct EntryListResponse: Codable, Equatable {
    let items: [Entry]
    let total: Int
    let limit: Int
    let offset: Int
}

struct EntryListQuery: Equatable {
    var startDate: String?
    var endDate: String?
    var kind: EntryKind?
    var tag: String?
    var currency: String?
    var source: String?
    var accountId: String?
    var limit: Int?
    var offset: Int?

    func queryItems() -> [URLQueryItem] {
        var items: [URLQueryItem] = []
        if let startDate {
            items.append(URLQueryItem(name: "start_date", value: startDate))
        }
        if let endDate {
            items.append(URLQueryItem(name: "end_date", value: endDate))
        }
        if let kind {
            items.append(URLQueryItem(name: "kind", value: kind.rawValue))
        }
        if let tag, !tag.isEmpty {
            items.append(URLQueryItem(name: "tag", value: tag))
        }
        if let currency, !currency.isEmpty {
            items.append(URLQueryItem(name: "currency", value: currency))
        }
        if let source, !source.isEmpty {
            items.append(URLQueryItem(name: "source", value: source))
        }
        if let accountId, !accountId.isEmpty {
            items.append(URLQueryItem(name: "account_id", value: accountId))
        }
        if let limit {
            items.append(URLQueryItem(name: "limit", value: String(limit)))
        }
        if let offset {
            items.append(URLQueryItem(name: "offset", value: String(offset)))
        }
        return items
    }
}

struct Reconciliation: Codable, Equatable {
    let accountId: String
    let accountName: String
    let currencyCode: String
    let asOf: String
    let ledgerBalanceMinor: Int
    let snapshotBalanceMinor: Int?
    let snapshotAt: String?
    let deltaMinor: Int?
}

struct DashboardKpis: Codable, Equatable {
    let expenseTotalMinor: Int
    let incomeTotalMinor: Int
    let netTotalMinor: Int
    let dailyExpenseTotalMinor: Int
    let nonDailyExpenseTotalMinor: Int
    let averageDailyExpenseMinor: Int
    let medianDailyExpenseMinor: Int
    let dailySpendingDays: Int
}

struct DashboardDailySpendingPoint: Codable, Equatable {
    let date: String
    let expenseTotalMinor: Int
    let dailyExpenseMinor: Int
    let nonDailyExpenseMinor: Int
}

struct DashboardMonthlyTrendPoint: Codable, Equatable {
    let month: String
    let expenseTotalMinor: Int
    let incomeTotalMinor: Int
    let dailyExpenseMinor: Int
    let nonDailyExpenseMinor: Int
}

struct DashboardBreakdownItem: Codable, Equatable {
    let label: String
    let totalMinor: Int
    let share: Double
}

struct DashboardWeekdaySpendingPoint: Codable, Equatable {
    let weekday: String
    let totalMinor: Int
}

struct DashboardLargestExpenseItem: Codable, Equatable {
    let id: String
    let occurredAt: String
    let name: String
    let toEntity: String?
    let amountMinor: Int
    let isDaily: Bool
}

struct DashboardProjection: Codable, Equatable {
    let isCurrentMonth: Bool
    let daysElapsed: Int
    let daysRemaining: Int
    let spentToDateMinor: Int
    let projectedTotalMinor: Int?
    let projectedRemainingMinor: Int?
}

struct Dashboard: Codable, Equatable {
    let month: String
    let currencyCode: String
    let kpis: DashboardKpis
    let dailySpending: [DashboardDailySpendingPoint]
    let monthlyTrend: [DashboardMonthlyTrendPoint]
    let spendingByFrom: [DashboardBreakdownItem]
    let spendingByTo: [DashboardBreakdownItem]
    let spendingByTag: [DashboardBreakdownItem]
    let weekdaySpending: [DashboardWeekdaySpendingPoint]
    let largestExpenses: [DashboardLargestExpenseItem]
    let projection: DashboardProjection
    let reconciliation: [Reconciliation]
}

struct RuntimeSettingsOverrides: Codable, Equatable {
    let userMemory: [String]?
    let defaultCurrencyCode: String?
    let dashboardCurrencyCode: String?
    let agentModel: String?
    let agentMaxSteps: Int?
    let agentBulkMaxConcurrentThreads: Int?
    let agentRetryMaxAttempts: Int?
    let agentRetryInitialWaitSeconds: Double?
    let agentRetryMaxWaitSeconds: Double?
    let agentRetryBackoffMultiplier: Double?
    let agentMaxImageSizeBytes: Int?
    let agentMaxImagesPerMessage: Int?
    let agentBaseURL: String?
    let agentApiKeyConfigured: Bool
}

struct RuntimeSettings: Codable, Equatable {
    let currentUserName: String
    let userMemory: [String]?
    let defaultCurrencyCode: String
    let dashboardCurrencyCode: String
    let agentModel: String
    let agentMaxSteps: Int
    let agentBulkMaxConcurrentThreads: Int
    let agentRetryMaxAttempts: Int
    let agentRetryInitialWaitSeconds: Double
    let agentRetryMaxWaitSeconds: Double
    let agentRetryBackoffMultiplier: Double
    let agentMaxImageSizeBytes: Int
    let agentMaxImagesPerMessage: Int
    let agentBaseURL: String?
    let agentApiKeyConfigured: Bool
    let overrides: RuntimeSettingsOverrides
}