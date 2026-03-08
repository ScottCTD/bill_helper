import Foundation
import SwiftUI

enum DashboardPhase: Equatable {
    case idle
    case loading
    case loaded(Dashboard)
    case empty(Dashboard)
    case failed(String)
}

@MainActor
final class DashboardScreenModel: ObservableObject {
    typealias Loader = @Sendable (String) async throws -> Dashboard

    @Published private(set) var phase: DashboardPhase = .idle

    let month: String
    private let loadDashboard: Loader

    init(month: String, loadDashboard: @escaping Loader) {
        self.month = month
        self.loadDashboard = loadDashboard
    }

    convenience init(loadDashboard: @escaping Loader) {
        self.init(month: Self.defaultMonthString(), loadDashboard: loadDashboard)
    }

    convenience init(apiClient: APIClient, month: String) {
        self.init(month: month) { requestedMonth in
            try await apiClient.dashboard(month: requestedMonth)
        }
    }

    convenience init(apiClient: APIClient) {
        self.init(apiClient: apiClient, month: Self.defaultMonthString())
    }

    func loadIfNeeded() async {
        guard case .idle = phase else { return }
        await reload()
    }

    func reload() async {
        phase = .loading
        do {
            let dashboard = try await loadDashboard(month)
            phase = dashboard.hasDisplayContent ? .loaded(dashboard) : .empty(dashboard)
        } catch {
            phase = .failed(Self.message(for: error))
        }
    }

    static func defaultMonthString(date: Date = .now) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM"
        return formatter.string(from: date)
    }

    private static func message(for error: Error) -> String {
        let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        return message.isEmpty ? "Couldn’t load the dashboard right now." : message
    }
}

enum EntriesPhase: Equatable {
    case idle
    case loading
    case loaded(EntryListResponse)
    case empty
    case failed(String)
}

@MainActor
final class EntriesScreenModel: ObservableObject {
    typealias Loader = @Sendable () async throws -> EntryListResponse

    @Published private(set) var phase: EntriesPhase = .idle

    private let loadEntries: Loader

    init(loadEntries: @escaping Loader) {
        self.loadEntries = loadEntries
    }

    convenience init(apiClient: APIClient) {
        self.init {
            try await apiClient.listEntries()
        }
    }

    func loadIfNeeded() async {
        guard case .idle = phase else { return }
        await reload()
    }

    func reload() async {
        phase = .loading
        do {
            let response = try await loadEntries()
            phase = response.items.isEmpty ? .empty : .loaded(response)
        } catch {
            phase = .failed(Self.message(for: error))
        }
    }

    private static func message(for error: Error) -> String {
        let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        return message.isEmpty ? "Couldn’t load entries right now." : message
    }
}

struct DashboardRootView: View {
    @StateObject private var model: DashboardScreenModel

    init(apiClient: APIClient) {
        _model = StateObject(wrappedValue: DashboardScreenModel(apiClient: apiClient))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                switch model.phase {
                case .idle, .loading:
                    DashboardLoadingView()
                case .failed(let message):
                    DashboardMessageView(
                        title: "Couldn’t load the dashboard",
                        systemImage: "wifi.exclamationmark",
                        message: message,
                        actionTitle: "Retry",
                        action: { await model.reload() }
                    )
                case .empty(let dashboard):
                    DashboardMessageView(
                        title: "Nothing to summarize yet",
                        systemImage: "chart.bar.xaxis",
                        message: "Once income, expenses, or reconciled accounts appear for \(FinanceDisplay.month(dashboard.month)), the monthly summary will show up here.",
                        actionTitle: "Refresh",
                        action: { await model.reload() }
                    )
                case .loaded(let dashboard):
                    DashboardLoadedView(dashboard: dashboard)
                }
            }
            .padding(20)
        }
        .background(Color(.systemGroupedBackground))
        .task { await model.loadIfNeeded() }
        .refreshable { await model.reload() }
    }
}

private struct DashboardLoadedView: View {
    let dashboard: Dashboard

    private let metrics = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            FeatureCard {
                VStack(alignment: .leading, spacing: 14) {
                    Text(FinanceDisplay.month(dashboard.month))
                        .font(.title2.weight(.semibold))
                    Text(dashboard.projectionSummary)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    HStack(alignment: .bottom, spacing: 12) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Spent so far")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.secondary)
                            Text(FinanceDisplay.currency(dashboard.projection.spentToDateMinor, currencyCode: dashboard.currencyCode))
                                .font(.system(.title, design: .rounded).weight(.bold))
                        }

                        Spacer()

                        Label(dashboard.reconciliation.isEmpty ? "No account snapshots" : "\(dashboard.reconciliation.count) accounts tracked", systemImage: "creditcard.and.123")
                            .font(.footnote.weight(.semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(.indigo.opacity(0.12), in: Capsule())
                    }
                }
            }

            LazyVGrid(columns: metrics, spacing: 12) {
                MetricTile(title: "Expenses", value: FinanceDisplay.currency(dashboard.kpis.expenseTotalMinor, currencyCode: dashboard.currencyCode), tint: .orange)
                MetricTile(title: "Income", value: FinanceDisplay.currency(dashboard.kpis.incomeTotalMinor, currencyCode: dashboard.currencyCode), tint: .mint)
                MetricTile(title: "Net", value: FinanceDisplay.signedCurrency(minor: dashboard.kpis.netTotalMinor, currencyCode: dashboard.currencyCode), tint: dashboard.kpis.netTotalMinor >= 0 ? .indigo : .red)
                MetricTile(title: "Daily spend days", value: "\(dashboard.kpis.dailySpendingDays)", tint: .blue)
            }

            if !dashboard.primaryBreakdown.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 14) {
                        SectionHeading(title: "Where spending went", subtitle: dashboard.primaryBreakdownTitle)
                        ForEach(Array(dashboard.primaryBreakdown.enumerated()), id: \.offset) { _, item in
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(item.label)
                                        .font(.subheadline.weight(.semibold))
                                    Spacer()
                                    Text(FinanceDisplay.currency(item.totalMinor, currencyCode: dashboard.currencyCode))
                                        .font(.subheadline.monospacedDigit())
                                        .foregroundStyle(.secondary)
                                }
                                ProgressView(value: min(max(item.share, 0), 1))
                                    .tint(.indigo)
                            }
                        }
                    }
                }
            }

            if !dashboard.largestExpenses.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 14) {
                        SectionHeading(title: "Largest expenses", subtitle: "The biggest recent outflows for quick mobile review.")
                        ForEach(Array(dashboard.largestExpenses.prefix(4)), id: \.id) { expense in
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: expense.isDaily ? "sun.max.fill" : "cart.fill")
                                    .foregroundStyle(expense.isDaily ? .yellow : .orange)
                                    .frame(width: 28, height: 28)
                                    .background(.quaternary, in: RoundedRectangle(cornerRadius: 10, style: .continuous))

                                VStack(alignment: .leading, spacing: 4) {
                                    Text(expense.name)
                                        .font(.subheadline.weight(.semibold))
                                    Text(expense.toEntity ?? "Unassigned destination")
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                    Text(FinanceDisplay.day(expense.occurredAt))
                                        .font(.footnote)
                                        .foregroundStyle(.tertiary)
                                }

                                Spacer()

                                Text(FinanceDisplay.currency(expense.amountMinor, currencyCode: dashboard.currencyCode))
                                    .font(.subheadline.monospacedDigit().weight(.semibold))
                            }
                        }
                    }
                }
            }

            if !dashboard.reconciliation.isEmpty {
                FeatureCard {
                    DashboardAccountsSection(accounts: dashboard.reconciliation)
                }
            }
        }
    }
}

private struct DashboardAccountsSection: View {
    let accounts: [Reconciliation]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeading(title: "Accounts", subtitle: "Quick reconciliation snapshot for active accounts in the dashboard currency.")

            ForEach(Array(accounts.indices), id: \.self) { index in
                DashboardAccountRow(account: accounts[index])
            }
        }
    }
}

private struct DashboardAccountRow: View {
    let account: Reconciliation

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(account.accountName)
                    .font(.subheadline.weight(.semibold))
                Text("As of \(FinanceDisplay.day(account.asOf))")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                Text(FinanceDisplay.currency(account.ledgerBalanceMinor, currencyCode: account.currencyCode))
                    .font(.subheadline.monospacedDigit().weight(.semibold))
                if let deltaMinor = account.deltaMinor {
                    Text(FinanceDisplay.signedCurrency(minor: deltaMinor, currencyCode: account.currencyCode))
                        .font(.footnote.monospacedDigit())
                        .foregroundStyle(deltaMinor == 0 ? AnyShapeStyle(.secondary) : AnyShapeStyle(Color.orange))
                }
            }
        }
    }
}

private struct DashboardLoadingView: View {
    var body: some View {
        FeatureCard {
            VStack(spacing: 16) {
                ProgressView()
                    .controlSize(.large)
                Text("Loading your monthly summary…")
                    .font(.headline)
                Text("We’re pulling the latest dashboard totals, spending highlights, and account balances.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 36)
        }
    }
}

private struct DashboardMessageView: View {
    let title: String
    let systemImage: String
    let message: String
    let actionTitle: String
    let action: @Sendable () async -> Void

    var body: some View {
        FeatureCard {
            ContentUnavailableView {
                Label(title, systemImage: systemImage)
            } description: {
                Text(message)
            } actions: {
                Button(actionTitle) {
                    Task { await action() }
                }
                .buttonStyle(.borderedProminent)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
        }
    }
}

struct EntriesRootView: View {
    @StateObject private var model: EntriesScreenModel

    init(apiClient: APIClient) {
        _model = StateObject(wrappedValue: EntriesScreenModel(apiClient: apiClient))
    }

    var body: some View {
        Group {
            switch model.phase {
            case .loaded(let response):
                EntriesListView(response: response, reload: { await model.reload() })
            case .idle, .loading:
                EntriesStateView(
                    title: "Loading entries…",
                    systemImage: "list.bullet.rectangle.portrait",
                    message: "Fetching the latest ledger rows for an at-a-glance mobile review.",
                    actionTitle: nil,
                    action: nil
                )
            case .empty:
                EntriesStateView(
                    title: "No entries yet",
                    systemImage: "tray",
                    message: "When ledger items exist for your current scope, they’ll appear here in a mobile-friendly list.",
                    actionTitle: "Refresh",
                    action: { await model.reload() }
                )
            case .failed(let message):
                EntriesStateView(
                    title: "Couldn’t load entries",
                    systemImage: "wifi.exclamationmark",
                    message: message,
                    actionTitle: "Retry",
                    action: { await model.reload() }
                )
            }
        }
        .background(Color(.systemGroupedBackground))
        .task { await model.loadIfNeeded() }
    }
}

private struct EntriesListView: View {
    let response: EntryListResponse
    let reload: @Sendable () async -> Void

    var body: some View {
        List {
            Section {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Recent entries")
                            .font(.title3.weight(.semibold))
                        Text(response.summaryText)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
                .listRowInsets(EdgeInsets(top: 10, leading: 0, bottom: 10, trailing: 0))
                .listRowBackground(Color.clear)
            }

            Section("Ledger") {
                ForEach(response.items, id: \.id) { entry in
                    NavigationLink {
                        EntryDetailView(entry: entry)
                    } label: {
                        EntryRowView(entry: entry)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color(.systemGroupedBackground))
        .refreshable { await reload() }
    }
}

private struct EntriesStateView: View {
    let title: String
    let systemImage: String
    let message: String
    let actionTitle: String?
    let action: (@Sendable () async -> Void)?

    var body: some View {
        ScrollView {
            FeatureCard {
                ContentUnavailableView {
                    Label(title, systemImage: systemImage)
                } description: {
                    Text(message)
                } actions: {
                    if let actionTitle, let action {
                        Button(actionTitle) {
                            Task { await action() }
                        }
                        .buttonStyle(.borderedProminent)
                    } else {
                        ProgressView()
                            .controlSize(.large)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 24)
            }
            .padding(20)
        }
        .refreshable {
            if let action {
                await action()
            }
        }
    }
}

private struct EntryRowView: View {
    let entry: Entry

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: entry.kind.symbol)
                .foregroundStyle(entry.kind.tint)
                .frame(width: 34, height: 34)
                .background(entry.kind.tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))

            VStack(alignment: .leading, spacing: 6) {
                Text(entry.name)
                    .font(.body.weight(.semibold))
                Text(entry.counterpartySummary)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                HStack(spacing: 8) {
                    Text(FinanceDisplay.day(entry.occurredAt))
                    if let tagSummary = entry.tagSummary {
                        Text("•")
                        Text(tagSummary)
                    }
                }
                .font(.footnote)
                .foregroundStyle(.tertiary)
            }

            Spacer(minLength: 12)

            VStack(alignment: .trailing, spacing: 6) {
                Text(FinanceDisplay.entryAmount(entry))
                    .font(.body.monospacedDigit().weight(.semibold))
                    .foregroundStyle(entry.kind.tint)
                Text(entry.kind.displayName)
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

private struct EntryDetailView: View {
    let entry: Entry

    var body: some View {
        List {
            Section("Overview") {
                detailRow("Amount", value: FinanceDisplay.entryAmount(entry))
                detailRow("Kind", value: entry.kind.displayName)
                detailRow("Occurred", value: FinanceDisplay.day(entry.occurredAt))
            }

            Section("Route") {
                detailRow("From", value: entry.fromEntity ?? missingLabel(isMissing: entry.fromEntityMissing, fallback: "Not set"))
                detailRow("To", value: entry.toEntity ?? missingLabel(isMissing: entry.toEntityMissing, fallback: "Not set"))
                if let owner = entry.owner {
                    detailRow("Owner", value: owner)
                }
            }

            if let directGroup = entry.directGroup {
                Section("Grouping") {
                    detailRow("Direct group", value: directGroup.name)
                    if !entry.groupPath.isEmpty {
                        detailRow("Path", value: entry.groupPath.map(\.name).joined(separator: " → "))
                    }
                }
            }

            if !entry.tags.isEmpty {
                Section("Tags") {
                    Text(entry.tags.map(\.name).joined(separator: ", "))
                }
            }

            if let notes = entry.markdownBody?.trimmingCharacters(in: .whitespacesAndNewlines), !notes.isEmpty {
                Section("Notes") {
                    Text(notes)
                        .textSelection(.enabled)
                }
            }
        }
        .navigationTitle(entry.name)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func detailRow(_ title: String, value: String) -> some View {
        HStack(alignment: .top) {
            Text(title)
                .foregroundStyle(.secondary)
            Spacer(minLength: 12)
            Text(value)
                .multilineTextAlignment(.trailing)
        }
    }

    private func missingLabel(isMissing: Bool, fallback: String) -> String {
        isMissing ? "Missing reference" : fallback
    }
}

private struct FeatureCard<Content: View>: View {
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct MetricTile: View {
    let title: String
    let value: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.monospacedDigit().weight(.semibold))
            RoundedRectangle(cornerRadius: 999, style: .continuous)
                .fill(tint.opacity(0.18))
                .frame(height: 6)
                .overlay(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 999, style: .continuous)
                        .fill(tint)
                        .frame(width: 44, height: 6)
                }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

private struct SectionHeading: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.headline)
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }
}

private enum FinanceDisplay {
    private static func makeCurrencyFormatter(currencyCode: String) -> NumberFormatter {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = currencyCode
        return formatter
    }

    private static func makeAPIDayFormatter() -> DateFormatter {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }

    private static func makeAPIMonthFormatter() -> DateFormatter {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM"
        return formatter
    }

    private static func makeMediumDayFormatter() -> DateFormatter {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter
    }

    private static func makeMonthDisplayFormatter() -> DateFormatter {
        let formatter = DateFormatter()
        formatter.dateFormat = "LLLL yyyy"
        return formatter
    }

    static func currency(_ minor: Int, currencyCode: String) -> String {
        let amount = NSDecimalNumber(value: Double(minor) / 100.0)
        return makeCurrencyFormatter(currencyCode: currencyCode).string(from: amount) ?? "\(currencyCode) \(minor)"
    }

    static func signedCurrency(minor: Int, currencyCode: String) -> String {
        if minor == 0 {
            return currency(0, currencyCode: currencyCode)
        }
        let prefix = minor > 0 ? "+" : "−"
        return "\(prefix)\(currency(abs(minor), currencyCode: currencyCode))"
    }

    static func entryAmount(_ entry: Entry) -> String {
        switch entry.kind {
        case .expense:
            return "−\(currency(entry.amountMinor, currencyCode: entry.currencyCode))"
        case .income:
            return "+\(currency(entry.amountMinor, currencyCode: entry.currencyCode))"
        case .transfer:
            return currency(entry.amountMinor, currencyCode: entry.currencyCode)
        }
    }

    static func day(_ rawValue: String) -> String {
        guard let date = makeAPIDayFormatter().date(from: rawValue) else { return rawValue }
        return makeMediumDayFormatter().string(from: date)
    }

    static func month(_ rawValue: String) -> String {
        guard let date = makeAPIMonthFormatter().date(from: rawValue) else { return rawValue }
        return makeMonthDisplayFormatter().string(from: date)
    }
}

private extension Dashboard {
    var hasDisplayContent: Bool {
        kpis.expenseTotalMinor != 0
            || kpis.incomeTotalMinor != 0
            || kpis.netTotalMinor != 0
            || !largestExpenses.isEmpty
            || !spendingByTo.isEmpty
            || !spendingByTag.isEmpty
            || !spendingByFrom.isEmpty
            || !reconciliation.isEmpty
    }

    var projectionSummary: String {
        guard let projectedTotalMinor = projection.projectedTotalMinor else {
            return "We’ll show a month-end projection once there’s enough activity to estimate the rest of the month."
        }
        return "Projected month-end spend is \(FinanceDisplay.currency(projectedTotalMinor, currencyCode: currencyCode)) with \(projection.daysRemaining) day\(projection.daysRemaining == 1 ? "" : "s") remaining."
    }

    var primaryBreakdown: [DashboardBreakdownItem] {
        if !spendingByTo.isEmpty {
            return Array(spendingByTo.prefix(4))
        }
        if !spendingByTag.isEmpty {
            return Array(spendingByTag.prefix(4))
        }
        return Array(spendingByFrom.prefix(4))
    }

    var primaryBreakdownTitle: String {
        if !spendingByTo.isEmpty {
            return "Top destinations by share of spend this month."
        }
        if !spendingByTag.isEmpty {
            return "Top tags by share of spend this month."
        }
        return "Top sources by share of spend this month."
    }
}

private extension EntryListResponse {
    var summaryText: String {
        if total == items.count {
            return "Showing all \(total) current entries in a mobile-first list."
        }
        return "Showing \(items.count) of \(total) entries. Pull to refresh for the latest results."
    }
}

private extension EntryKind {
    var displayName: String {
        switch self {
        case .expense: "Expense"
        case .income: "Income"
        case .transfer: "Transfer"
        }
    }

    var symbol: String {
        switch self {
        case .expense: "arrow.down.right.circle.fill"
        case .income: "arrow.up.right.circle.fill"
        case .transfer: "arrow.left.arrow.right.circle.fill"
        }
    }

    var tint: Color {
        switch self {
        case .expense: .orange
        case .income: .mint
        case .transfer: .blue
        }
    }
}

private extension Entry {
    var counterpartySummary: String {
        switch kind {
        case .expense:
            return toEntity ?? fromEntity ?? "Unassigned destination"
        case .income:
            return fromEntity ?? toEntity ?? "Unassigned source"
        case .transfer:
            let entities = [fromEntity, toEntity].compactMap { $0 }
            return entities.isEmpty ? "Account transfer" : entities.joined(separator: " → ")
        }
    }

    var tagSummary: String? {
        let names = Array(tags.prefix(2)).map(\.name)
        guard !names.isEmpty else { return nil }
        return names.joined(separator: ", ")
    }
}