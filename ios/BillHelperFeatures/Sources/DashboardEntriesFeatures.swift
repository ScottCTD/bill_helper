import Charts
import SwiftUI
import UIKit

@MainActor
final class DashboardScreenModel: ObservableObject {
    @Published private(set) var timelineMonths: [String] = []
    @Published private(set) var phase: DashboardPhase = .idle
    @Published var selectedMonth: String = DashboardScreenModel.defaultMonthString()
    @Published var selectedFilterGroupKey: String?

    private let apiClient: APIClient
    private var hasLoaded = false

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        await reload()
    }

    func reload() async {
        phase = .loading
        do {
            let timeline = try await apiClient.dashboardTimeline()
            timelineMonths = timeline.months
            if !timelineMonths.contains(selectedMonth), let fallback = timelineMonths.last {
                selectedMonth = fallback
            }
            let dashboard = try await apiClient.dashboard(month: selectedMonth)
            phase = dashboard.hasDisplayContent ? .loaded(dashboard) : .empty(dashboard)
            if dashboard.filterGroups.contains(where: { $0.key == selectedFilterGroupKey }) == false {
                selectedFilterGroupKey = dashboard.filterGroups.first?.key
            }
            hasLoaded = true
        } catch {
            phase = .failed(Self.message(for: error))
        }
    }

    func select(month: String) async {
        guard selectedMonth != month else { return }
        selectedMonth = month
        await reload()
    }

    func handle(deepLink: AppDeepLink?) async {
        guard case .dashboard(let month)? = deepLink else { return }
        if let month, !month.isEmpty {
            selectedMonth = month
        }
        await reload()
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

enum DashboardPhase: Equatable {
    case idle
    case loading
    case loaded(Dashboard)
    case empty(Dashboard)
    case failed(String)
}

struct DashboardRootView: View {
    private let apiClient: APIClient
    @StateObject private var model: DashboardScreenModel
    @Binding private var deepLink: AppDeepLink?

    init(apiClient: APIClient, deepLink: Binding<AppDeepLink?>) {
        self.apiClient = apiClient
        _model = StateObject(wrappedValue: DashboardScreenModel(apiClient: apiClient))
        _deepLink = deepLink
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                monthPicker

                switch model.phase {
                case .idle, .loading:
                    InfoStateCard(title: "Loading dashboard…", message: "Pulling the latest month summary, filter groups, and reconciliation state.", symbol: "chart.bar")
                case .failed(let message):
                    ErrorStateCard(title: "Couldn’t load the dashboard", message: message) {
                        await model.reload()
                    }
                case .empty(let dashboard):
                    InfoStateCard(title: "Nothing to summarize yet", message: "No visible activity is available for \(FinanceFormatters.monthLabel(for: dashboard.month)).", symbol: "tray")
                case .loaded(let dashboard):
                    DashboardLoadedView(
                        apiClient: apiClient,
                        dashboard: dashboard,
                        selectedFilterGroupKey: $model.selectedFilterGroupKey
                    )
                }
            }
            .padding(20)
        }
        .background(Color(.systemGroupedBackground))
        .task { await model.loadIfNeeded() }
        .refreshable { await model.reload() }
        .onChange(of: deepLink) { _, newValue in
            guard newValue?.destination == .dashboard else { return }
            Task {
                await model.handle(deepLink: newValue)
                deepLink = nil
            }
        }
    }

    private var monthPicker: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(model.timelineMonths.isEmpty ? [model.selectedMonth] : model.timelineMonths, id: \.self) { month in
                        Button {
                            Task { await model.select(month: month) }
                        } label: {
                            Text(FinanceFormatters.monthLabel(for: month))
                                .font(.subheadline.weight(.semibold))
                                .padding(.horizontal, 14)
                                .padding(.vertical, 10)
                                .background(month == model.selectedMonth ? Color.indigo : Color(.secondarySystemGroupedBackground), in: Capsule())
                                .foregroundStyle(month == model.selectedMonth ? .white : .primary)
                        }
                        .buttonStyle(.plain)
                        .id(month)
                    }
                }
            }
            .onAppear {
                scrollMonthStrip(with: proxy)
            }
            .onChange(of: model.selectedMonth) { _, _ in
                scrollMonthStrip(with: proxy)
            }
            .onChange(of: model.timelineMonths) { _, _ in
                scrollMonthStrip(with: proxy)
            }
        }
    }

    private func scrollMonthStrip(with proxy: ScrollViewProxy) {
        let availableMonths = DashboardMonthPickerState.availableMonths(
            timelineMonths: model.timelineMonths,
            selectedMonth: model.selectedMonth
        )
        guard availableMonths.contains(model.selectedMonth) else { return }
        withAnimation(.snappy(duration: 0.24)) {
            proxy.scrollTo(model.selectedMonth, anchor: .center)
        }
    }
}

private struct DashboardLoadedView: View {
    let apiClient: APIClient
    let dashboard: Dashboard
    @Binding var selectedFilterGroupKey: String?

    private var selectedFilterGroup: DashboardFilterGroupSummary? {
        if let selectedFilterGroupKey,
           let matched = dashboard.filterGroups.first(where: { $0.key == selectedFilterGroupKey }) {
            return matched
        }
        return dashboard.filterGroups.first
    }

    private var selectedFilterGroupColor: Color {
        dashboardColor(for: selectedFilterGroup?.color, fallback: .indigo)
    }

    private var highlightedLargestExpenses: [DashboardLargestExpenseItem] {
        guard let selectedFilterGroup else { return dashboard.largestExpenses }
        let filtered = dashboard.largestExpenses.filter { $0.matchingFilterGroupKeys.contains(selectedFilterGroup.key) }
        return filtered.isEmpty ? dashboard.largestExpenses : filtered
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            DashboardHeroCard(dashboard: dashboard, selectedFilterGroup: selectedFilterGroup)
            DashboardProjectionCard(dashboard: dashboard, selectedFilterGroup: selectedFilterGroup)

            if !dashboard.filterGroups.isEmpty {
                DashboardFilterGroupSelector(
                    dashboard: dashboard,
                    selectedFilterGroup: selectedFilterGroup,
                    selectedFilterGroupKey: $selectedFilterGroupKey
                )
            }

            if !dashboard.monthlyTrend.isEmpty {
                DashboardMonthlyTrendChart(
                    dashboard: dashboard,
                    selectedFilterGroup: selectedFilterGroup,
                    tint: selectedFilterGroupColor
                )
            }

            if !dashboard.dailySpending.isEmpty {
                DashboardDailyChart(
                    dashboard: dashboard,
                    selectedFilterGroup: selectedFilterGroup,
                    tint: selectedFilterGroupColor
                )
            }

            if !dashboard.filterGroups.isEmpty {
                DashboardFilterGroupDistributionChart(
                    dashboard: dashboard,
                    selectedFilterGroup: selectedFilterGroup,
                    tint: selectedFilterGroupColor
                )
            }

            if !dashboard.spendingByTo.isEmpty || !dashboard.spendingByFrom.isEmpty || !dashboard.spendingByTag.isEmpty {
                DashboardBreakdownsSection(dashboard: dashboard)
            }

            if !dashboard.weekdaySpending.isEmpty {
                DashboardWeekdayChart(dashboard: dashboard)
            }

            if !highlightedLargestExpenses.isEmpty {
                DashboardLargestExpensesCard(
                    expenses: highlightedLargestExpenses,
                    dashboard: dashboard,
                    selectedFilterGroup: selectedFilterGroup,
                    tint: selectedFilterGroupColor
                )
            }

            if !dashboard.reconciliation.isEmpty {
                DashboardReconciliationCard(apiClient: apiClient, accounts: dashboard.reconciliation)
            }
        }
        .onAppear(perform: syncSelectedFilterGroup)
        .onChange(of: dashboard.filterGroups.map(\.key)) { _, _ in
            syncSelectedFilterGroup()
        }
    }

    private func syncSelectedFilterGroup() {
        if dashboard.filterGroups.contains(where: { $0.key == selectedFilterGroupKey }) == false {
            selectedFilterGroupKey = dashboard.filterGroups.first?.key
        }
    }
}

private struct DashboardAccountRow: View {
    let account: DashboardReconciliation

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(spacing: 8) {
                Image(systemName: account.mismatchedIntervalCount > 0 ? "exclamationmark.triangle.fill" : "checkmark.seal.fill")
                    .font(.headline)
                    .foregroundStyle(account.mismatchedIntervalCount > 0 ? Color.orange : Color.green)
                    .frame(width: 40, height: 40)
                    .background(
                        (account.mismatchedIntervalCount > 0 ? Color.orange : Color.green).opacity(0.14),
                        in: RoundedRectangle(cornerRadius: 14, style: .continuous)
                    )
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(account.accountName)
                    .font(.subheadline.weight(.semibold))
                Text(account.latestSnapshotAt.map { "Snapshot \(FinanceFormatters.dayLabel(for: $0))" } ?? "No snapshots yet")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                HStack(spacing: 8) {
                    DashboardContextPill(
                        title: "\(account.reconciledIntervalCount) matched",
                        tint: .green
                    )
                    if account.mismatchedIntervalCount > 0 {
                        DashboardContextPill(
                            title: "\(account.mismatchedIntervalCount) mismatched",
                            tint: .orange
                        )
                    }
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(FinanceFormatters.signedCurrency(account.currentTrackedChangeMinor ?? 0, currencyCode: account.currencyCode))
                    .font(.subheadline.monospacedDigit())
                Text(
                    account.lastClosedDeltaMinor.map {
                        "Last delta \(FinanceFormatters.signedCurrency($0, currencyCode: account.currencyCode))"
                    } ?? "Open interval"
                )
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

@MainActor
final class EntriesScreenModel: ObservableObject {
    @Published private(set) var phase: EntriesPhase = .idle
    @Published private(set) var tags: [Tag] = []
    @Published private(set) var groups: [GroupSummary] = []
    @Published private(set) var entities: [Entity] = []
    @Published private(set) var users: [User] = []
    @Published private(set) var currencies: [Currency] = []
    @Published private(set) var filterGroups: [FilterGroup] = []

    private let apiClient: APIClient
    private var hasLoaded = false

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        await reload()
    }

    func reload() async {
        phase = .loading
        do {
            async let entriesTask = apiClient.listEntries(query: EntryListQuery(limit: 200, offset: 0))
            async let tagsTask = apiClient.listTags()
            async let groupsTask = apiClient.listGroups()
            async let entitiesTask = apiClient.listEntities()
            async let usersTask = apiClient.listUsers()
            async let currenciesTask = apiClient.listCurrencies()
            async let filterGroupsTask = apiClient.listFilterGroups()

            let response = try await entriesTask
            tags = try await tagsTask
            groups = try await groupsTask
            entities = try await entitiesTask
            users = try await usersTask
            currencies = try await currenciesTask
            filterGroups = try await filterGroupsTask
            phase = response.items.isEmpty ? .empty : .loaded(response)
            hasLoaded = true
        } catch {
            phase = .failed(Self.message(for: error))
        }
    }

    func createEntry(_ payload: EntryCreatePayload) async throws {
        _ = try await apiClient.createEntry(payload)
        await reload()
    }

    func updateEntry(id: String, payload: EntryUpdatePayload) async throws {
        _ = try await apiClient.updateEntry(id: id, payload: payload)
        await reload()
    }

    func deleteEntry(id: String) async throws {
        try await apiClient.deleteEntry(id: id)
        await reload()
    }

    func loadEntry(id: String) async throws -> EntryDetail {
        try await apiClient.entry(id: id)
    }

    private static func message(for error: Error) -> String {
        let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        return message.isEmpty ? "Couldn’t load entries right now." : message
    }
}

enum EntriesPhase: Equatable {
    case idle
    case loading
    case loaded(EntryListResponse)
    case empty
    case failed(String)
}

private enum EntryEditorMode: Equatable, Identifiable {
    case create
    case edit(Entry)

    var id: String {
        switch self {
        case .create:
            return "create"
        case .edit(let entry):
            return "edit-\(entry.id)"
        }
    }
}

struct EntriesRootView: View {
    @StateObject private var model: EntriesScreenModel
    @Binding private var deepLink: AppDeepLink?
    @State private var searchText = ""
    @State private var selectedKind: EntryKind?
    @State private var selectedTagNames: [String] = []
    @State private var selectedCurrencyCode: String?
    @State private var selectedSource = ""
    @State private var selectedFilterGroupID: String?
    @State private var editorMode: EntryEditorMode?
    @State private var deletionTarget: Entry?
    @State private var path: [String] = []
    @State private var editorError: String?
    @State private var isTagFilterPickerPresented = false

    init(apiClient: APIClient, deepLink: Binding<AppDeepLink?>) {
        _model = StateObject(wrappedValue: EntriesScreenModel(apiClient: apiClient))
        _deepLink = deepLink
    }

    var body: some View {
        content
            .navigationDestination(for: String.self) { entryID in
                EntryDetailContainerView(entryID: entryID, model: model) { entry in
                    editorMode = .edit(entry)
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editorMode = .create
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .searchable(text: $searchText, prompt: "Search entries")
            .task { await model.loadIfNeeded() }
            .refreshable { await model.reload() }
            .sheet(item: $editorMode) { _ in
                EntryEditorSheet(
                    mode: editorMode ?? .create,
                    model: model,
                    errorMessage: $editorError
                ) {
                    editorMode = nil
                }
            }
            .sheet(isPresented: $isTagFilterPickerPresented) {
                EntryTagPickerSheet(
                    title: "Filter Tags",
                    subtitle: "Match entries that contain any selected tag.",
                    tags: model.tags,
                    selection: $selectedTagNames,
                    allowCreate: false
                )
            }
            .alert("Delete entry?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
                Button("Delete", role: .destructive) {
                    guard let target = deletionTarget else { return }
                    Task {
                        do {
                            try await model.deleteEntry(id: target.id)
                            FinanceFeedback.destructive()
                        } catch {
                            editorError = error.localizedDescription
                            FinanceFeedback.error()
                        }
                        deletionTarget = nil
                    }
                }
                Button("Cancel", role: .cancel) {
                    deletionTarget = nil
                }
            } message: {
                Text("This removes the entry from the visible ledger list.")
            }
            .onChange(of: deepLink) { _, newValue in
                guard case .entry(let id)? = newValue else { return }
                path = [id]
                deepLink = nil
            }
    }

    private var content: some View {
        Group {
            switch model.phase {
            case .idle, .loading:
                InfoStateCard(title: "Loading entries…", message: "Fetching the current ledger rows and editor resources.", symbol: "list.bullet.rectangle")
            case .empty:
                InfoStateCard(title: "No entries yet", message: "Create an entry or wait for agent-reviewed items to be applied.", symbol: "tray")
            case .failed(let message):
                ErrorStateCard(title: "Couldn’t load entries", message: message) {
                    await model.reload()
                }
            case .loaded(let response):
                List {
                    filterSection
                    Section("Ledger") {
                        ForEach(filteredEntries(from: response.items), id: \.id) { entry in
                            NavigationLink(value: entry.id) {
                                EntryRowView(entry: entry)
                            }
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    deletionTarget = entry
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                            .swipeActions(edge: .leading) {
                                Button {
                                    editorMode = .edit(entry)
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(.indigo)
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }
        }
        .background(Color(.systemGroupedBackground))
    }

    private var filterSection: some View {
        Section("Filters") {
            Picker("Kind", selection: Binding(get: { selectedKind }, set: { selectedKind = $0 })) {
                Text("All").tag(EntryKind?.none)
                ForEach(EntryKind.allCases, id: \.self) { kind in
                    Text(kind.displayName).tag(Optional(kind))
                }
            }

            Button {
                isTagFilterPickerPresented = true
            } label: {
                HStack {
                    Text("Tags")
                    Spacer()
                    if selectedTagNames.isEmpty {
                        Text("All")
                            .foregroundStyle(.secondary)
                    } else {
                        Text("\(selectedTagNames.count) selected")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .buttonStyle(.plain)

            if !selectedTagNames.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(EntryTagSelection.displayTags(tags: model.tags, selected: selectedTagNames), id: \.key) { tag in
                            EntryTagChip(tag: tag, removable: false)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }

            Picker("Currency", selection: Binding(get: { selectedCurrencyCode }, set: { selectedCurrencyCode = $0 })) {
                Text("All").tag(String?.none)
                ForEach(model.currencies.map(\.code), id: \.self) { code in
                    Text(code).tag(Optional(code))
                }
            }

            Picker("Filter group", selection: Binding(get: { selectedFilterGroupID }, set: { selectedFilterGroupID = $0 })) {
                Text("All").tag(String?.none)
                ForEach(model.filterGroups, id: \.id) { group in
                    Text(group.name).tag(Optional(group.id))
                }
            }

            TextField("Source contains", text: $selectedSource)

            if hasActiveFilters {
                Button("Clear filters") {
                    selectedKind = nil
                    selectedTagNames = []
                    selectedCurrencyCode = nil
                    selectedSource = ""
                    selectedFilterGroupID = nil
                }
                .foregroundStyle(.red)
            }
        }
    }

    private func filteredEntries(from entries: [Entry]) -> [Entry] {
        entries.filter { entry in
            if !searchText.isEmpty {
                let haystack = [entry.name, entry.fromEntity ?? "", entry.toEntity ?? "", entry.owner ?? "", entry.tags.map(\.name).joined(separator: " ")]
                    .joined(separator: " ")
                    .lowercased()
                guard haystack.contains(searchText.lowercased()) else { return false }
            }
            if let selectedKind, entry.kind != selectedKind {
                return false
            }
            if !selectedTagNames.isEmpty {
                let selectedTagSet = Set(selectedTagNames.map(EntryTagSelection.normalizeTagName))
                guard entry.tags.contains(where: { selectedTagSet.contains(EntryTagSelection.normalizeTagName($0.name)) }) else {
                    return false
                }
            }
            if let selectedCurrencyCode, entry.currencyCode != selectedCurrencyCode {
                return false
            }
            if !selectedSource.isEmpty {
                let sourceText = (entry.fromEntity ?? "") + " " + (entry.toEntity ?? "")
                guard sourceText.localizedCaseInsensitiveContains(selectedSource) else { return false }
            }
            if let selectedFilterGroupID, !(entry.groupPath.contains { $0.id == selectedFilterGroupID } || entry.directGroup?.id == selectedFilterGroupID) {
                return false
            }
            return true
        }
    }

    private var hasActiveFilters: Bool {
        selectedKind != nil
            || !selectedTagNames.isEmpty
            || selectedCurrencyCode != nil
            || !selectedSource.isEmpty
            || selectedFilterGroupID != nil
    }
}

private struct EntryRowView: View {
    let entry: Entry

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: entry.kind.symbolName)
                .foregroundStyle(entry.kind.tintColor)
                .frame(width: 34, height: 34)
                .background(entry.kind.tintColor.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))

            VStack(alignment: .leading, spacing: 6) {
                Text(entry.name)
                    .font(.body.weight(.semibold))
                Text(entry.counterpartySummary)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(entry.tagSummary ?? FinanceFormatters.dayLabel(for: entry.occurredAt))
                    .font(.footnote)
                    .foregroundStyle(.tertiary)
            }

            Spacer()

            Text(FinanceFormatters.signedCurrency(entry.kind == .expense ? -entry.amountMinor : entry.amountMinor, currencyCode: entry.currencyCode))
                .font(.body.monospacedDigit().weight(.semibold))
                .foregroundStyle(entry.kind.tintColor)
        }
        .padding(.vertical, 4)
    }
}

private struct EntryDetailContainerView: View {
    let entryID: String
    @ObservedObject var model: EntriesScreenModel
    let onEdit: (Entry) -> Void
    @State private var entry: Entry?
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if let entry {
                List {
                    Section("Overview") {
                        LabeledContent("Amount", value: FinanceFormatters.currency(entry.amountMinor, currencyCode: entry.currencyCode))
                        LabeledContent("Kind", value: entry.kind.displayName)
                        LabeledContent("Occurred", value: FinanceFormatters.dayLabel(for: entry.occurredAt))
                    }
                    Section("Route") {
                        LabeledContent("From", value: entry.fromEntity ?? "Not set")
                        LabeledContent("To", value: entry.toEntity ?? "Not set")
                        if let owner = entry.owner {
                            LabeledContent("Owner", value: owner)
                        }
                    }
                    if let directGroup = entry.directGroup {
                        Section("Grouping") {
                            LabeledContent("Direct group", value: directGroup.name)
                            if let role = entry.directGroupMemberRole {
                                LabeledContent("Role", value: role.rawValue)
                            }
                        }
                    }
                    if !entry.tags.isEmpty {
                        Section("Tags") {
                            EntryTagChipGrid(
                                tags: EntryTagSelection.displayTags(tags: entry.tags, selected: entry.tags.map(\.name))
                            ) { _ in }
                        }
                    }
                    if let notes = entry.markdownBody, !notes.isEmpty {
                        Section("Notes") {
                            AgentMarkdownText(
                                rendered: AssistantMessageMarkdownRenderer.renderedContent(
                                    forMarkdown: notes,
                                    messageID: entry.id
                                ),
                                tint: .indigo
                            )
                        }
                    }
                }
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Edit") {
                            onEdit(entry)
                        }
                    }
                }
            } else if let errorMessage {
                ErrorStateCard(title: "Couldn’t load entry", message: errorMessage) {
                    await load()
                }
            } else {
                InfoStateCard(title: "Loading entry…", message: "Fetching the latest entry detail.", symbol: "list.bullet.rectangle")
            }
        }
        .navigationTitle("Entry")
        .task { await load() }
    }

    private func load() async {
        do {
            entry = try await model.loadEntry(id: entryID)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct EntryEditorSheet: View {
    let mode: EntryEditorMode
    @ObservedObject var model: EntriesScreenModel
    @Binding var errorMessage: String?
    let onDismiss: () -> Void

    @State private var kind: EntryKind = .expense
    @State private var occurredDate = Date()
    @State private var name = ""
    @State private var amountMajor = ""
    @State private var currencyCode = "CAD"
    @State private var fromEntityID = ""
    @State private var toEntityID = ""
    @State private var ownerUserID = ""
    @State private var fromEntityText = ""
    @State private var toEntityText = ""
    @State private var ownerText = ""
    @State private var markdownBody = ""
    @State private var selectedTags: [String] = []
    @State private var directGroupID = ""
    @State private var directGroupRole: GroupMemberRole = .child
    @State private var isSaving = false
    @State private var isTagPickerPresented = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Entry") {
                    Picker("Kind", selection: $kind) {
                        ForEach(EntryKind.allCases, id: \.self) { kind in
                            Text(kind.displayName).tag(kind)
                        }
                    }
                    DatePicker("Occurred on", selection: $occurredDate, displayedComponents: .date)
                    TextField("Name", text: $name)
                    TextField("Amount", text: $amountMajor)
                        .keyboardType(.decimalPad)
                    Picker("Currency", selection: $currencyCode) {
                        ForEach(model.currencies.map(\.code), id: \.self) { code in
                            Text(code).tag(code)
                        }
                    }
                }

                Section("Route") {
                    Picker("From entity", selection: $fromEntityID) {
                        Text("None").tag("")
                        ForEach(model.entities, id: \.id) { entity in
                            Text(entity.name).tag(entity.id)
                        }
                    }
                    TextField("From fallback label", text: $fromEntityText)

                    Picker("To entity", selection: $toEntityID) {
                        Text("None").tag("")
                        ForEach(model.entities, id: \.id) { entity in
                            Text(entity.name).tag(entity.id)
                        }
                    }
                    TextField("To fallback label", text: $toEntityText)

                    Picker("Owner", selection: $ownerUserID) {
                        Text("Auto").tag("")
                        ForEach(model.users, id: \.id) { user in
                            Text(user.name).tag(user.id)
                        }
                    }
                    TextField("Owner fallback label", text: $ownerText)
                }

                Section("Grouping") {
                    Picker("Direct group", selection: $directGroupID) {
                        Text("None").tag("")
                        ForEach(model.groups, id: \.id) { group in
                            Text(group.name).tag(group.id)
                        }
                    }
                    if selectedGroup?.groupType == .split {
                        Picker("Split role", selection: $directGroupRole) {
                            ForEach(GroupMemberRole.allCases, id: \.self) { role in
                                Text(role.rawValue.capitalized).tag(role)
                            }
                        }
                        Text("Split groups require a member role. Use Parent for the shared source row and Child for the allocated portion.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        Text("Each entry can belong to one direct group. Choose a child group if you want the parent path to be derived automatically.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Tags") {
                    if selectedTags.isEmpty {
                        Text("No tags selected yet. Tags improve dashboard classification and entry search.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        EntryTagChipGrid(
                            tags: EntryTagSelection.displayTags(tags: model.tags, selected: selectedTags)
                        ) { tagKey in
                            selectedTags = EntryTagSelection.remove(tagKey, from: selectedTags)
                        }
                    }

                    Button(selectedTags.isEmpty ? "Add Tags" : "Manage Tags") {
                        isTagPickerPresented = true
                    }

                    Text("Tag names are normalized to lowercase on save. New tags are created automatically if they do not already exist.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("Notes") {
                    TextEditor(text: $markdownBody)
                        .frame(minHeight: 120)
                    Text("Markdown is supported for longer notes.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onDismiss)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
            .sheet(isPresented: $isTagPickerPresented) {
                EntryTagPickerSheet(
                    title: "Tags",
                    subtitle: "Select existing tags or create new ones for this entry.",
                    tags: model.tags,
                    selection: $selectedTags,
                    allowCreate: true
                )
            }
            .onAppear(perform: populateIfNeeded)
            .onChange(of: directGroupID) { _, newValue in
                if newValue.isEmpty || selectedGroup?.groupType != .split {
                    directGroupRole = .child
                }
            }
        }
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New Entry"
        case .edit:
            return "Edit Entry"
        }
    }

    private var selectedGroup: GroupSummary? {
        model.groups.first(where: { $0.id == directGroupID })
    }

    private func populateIfNeeded() {
        if case .edit(let entry) = mode {
            kind = entry.kind
            occurredDate = FinanceFormatters.dayInputFormatter.date(from: entry.occurredAt) ?? .now
            name = entry.name
            amountMajor = String(format: "%.2f", Double(entry.amountMinor) / 100)
            currencyCode = entry.currencyCode
            fromEntityID = entry.fromEntityId ?? ""
            toEntityID = entry.toEntityId ?? ""
            ownerUserID = entry.ownerUserId ?? ""
            fromEntityText = entry.fromEntity ?? ""
            toEntityText = entry.toEntity ?? ""
            ownerText = entry.owner ?? ""
            markdownBody = entry.markdownBody ?? ""
            selectedTags = EntryTagSelection.normalize(entry.tags.map(\.name))
            directGroupID = entry.directGroup?.id ?? ""
            directGroupRole = entry.directGroupMemberRole ?? .child
            return
        }

        if model.currencies.contains(where: { $0.code == currencyCode }) == false,
           let preferredCurrency = model.currencies.first?.code {
            currencyCode = preferredCurrency
        }
    }

    private func save() async {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty else {
            errorMessage = "Name is required."
            FinanceFeedback.error()
            return
        }

        let normalizedAmountText = amountMajor.replacingOccurrences(of: ",", with: "")
        let amountMinor = Int(((Double(normalizedAmountText) ?? 0) * 100).rounded())
        guard amountMinor > 0 else {
            errorMessage = "Enter a valid amount."
            FinanceFeedback.error()
            return
        }

        guard !currencyCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            errorMessage = "Select a currency."
            FinanceFeedback.error()
            return
        }

        let occurredAt = FinanceFormatters.dayInputFormatter.string(from: occurredDate)
        let normalizedTags = EntryTagSelection.normalize(selectedTags)

        isSaving = true
        defer { isSaving = false }

        do {
            switch mode {
            case .create:
                try await model.createEntry(
                    EntryCreatePayload(
                        accountId: nil,
                        kind: kind,
                        occurredAt: occurredAt,
                        name: trimmedName,
                        amountMinor: amountMinor,
                        currencyCode: currencyCode,
                        fromEntityId: fromEntityID.isEmpty ? nil : fromEntityID,
                        toEntityId: toEntityID.isEmpty ? nil : toEntityID,
                        ownerUserId: ownerUserID.isEmpty ? nil : ownerUserID,
                        fromEntity: fromEntityText.emptyAsNil,
                        toEntity: toEntityText.emptyAsNil,
                        owner: ownerText.emptyAsNil,
                        markdownBody: markdownBody.emptyAsNil,
                        tags: normalizedTags,
                        directGroupId: directGroupID.emptyAsNil,
                        directGroupMemberRole: selectedGroup?.groupType == .split ? directGroupRole : nil
                    )
                )
            case .edit(let entry):
                try await model.updateEntry(
                    id: entry.id,
                    payload: EntryUpdatePayload(
                        accountId: entry.accountId,
                        kind: kind,
                        occurredAt: occurredAt,
                        name: trimmedName,
                        amountMinor: amountMinor,
                        currencyCode: currencyCode,
                        fromEntityId: fromEntityID.emptyAsNil,
                        toEntityId: toEntityID.emptyAsNil,
                        ownerUserId: ownerUserID.emptyAsNil,
                        fromEntity: fromEntityText.emptyAsNil,
                        toEntity: toEntityText.emptyAsNil,
                        owner: ownerText.emptyAsNil,
                        markdownBody: markdownBody.emptyAsNil,
                        tags: normalizedTags,
                        directGroupId: directGroupID.emptyAsNil,
                        directGroupMemberRole: selectedGroup?.groupType == .split ? directGroupRole : nil
                    )
                )
            }
            errorMessage = nil
            FinanceFeedback.success()
            onDismiss()
        } catch {
            errorMessage = error.localizedDescription
            FinanceFeedback.error()
        }
    }
}

struct AccountDetailView: View {
    let apiClient: APIClient
    let accountID: String
    @State private var account: Account?
    @State private var snapshots: [Snapshot] = []
    @State private var reconciliation: Reconciliation?
    @State private var errorMessage: String?
    @State private var isLoading = true

    init(apiClient: APIClient, accountID: String = "") {
        self.apiClient = apiClient
        self.accountID = accountID
    }

    var body: some View {
        Group {
            if isLoading {
                InfoStateCard(title: "Loading account…", message: "Fetching snapshots and reconciliation intervals.", symbol: "creditcard")
            } else if let errorMessage {
                ErrorStateCard(title: "Couldn’t load account", message: errorMessage) {
                    await load()
                }
            } else {
                List {
                    if let account {
                        Section("Account") {
                            LabeledContent("Name", value: account.name)
                            LabeledContent("Currency", value: account.currencyCode)
                            LabeledContent("Active", value: account.isActive ? "Yes" : "No")
                        }
                    }
                    if !snapshots.isEmpty {
                        Section("Snapshots") {
                            ForEach(snapshots, id: \.id) { snapshot in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(snapshot.snapshotAt)
                                    Text(FinanceFormatters.currency(snapshot.balanceMinor, currencyCode: account?.currencyCode ?? "CAD"))
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    if let reconciliation {
                        Section("Reconciliation") {
                            ForEach(reconciliation.intervals, id: \.startSnapshot.id) { interval in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("\(interval.startSnapshot.snapshotAt) → \(interval.endSnapshot?.snapshotAt ?? "Open")")
                                    Text("Tracked \(FinanceFormatters.signedCurrency(interval.trackedChangeMinor, currencyCode: reconciliation.currencyCode))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(account?.name ?? "Account")
        .task { await load() }
    }

    private func load() async {
        guard !accountID.isEmpty else {
            errorMessage = "Missing account identifier."
            isLoading = false
            return
        }
        isLoading = true
        do {
            let accounts = try await apiClient.listAccounts()
            account = accounts.first(where: { $0.id == accountID })
            guard account != nil else {
                errorMessage = "This account is no longer available."
                snapshots = []
                reconciliation = nil
                isLoading = false
                return
            }
            async let snapshotsTask = apiClient.listAccountSnapshots(accountID: accountID)
            async let reconciliationTask = apiClient.accountReconciliation(accountID: accountID)
            snapshots = try await snapshotsTask
            reconciliation = try await reconciliationTask
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

private struct FeatureCard<Content: View>: View {
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct StatPill: View {
    let title: String
    let value: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline.monospacedDigit().weight(.semibold))
                .foregroundStyle(tint)
        }
        .padding(12)
        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

private struct InfoStateCard: View {
    let title: String
    let message: String
    let symbol: String

    var body: some View {
        FeatureCard {
            ContentUnavailableView {
                Label(title, systemImage: symbol)
            } description: {
                Text(message)
            }
        }
        .padding(.top, 10)
    }
}

private struct ErrorStateCard: View {
    let title: String
    let message: String
    let retry: @Sendable () async -> Void

    var body: some View {
        FeatureCard {
            ContentUnavailableView {
                Label(title, systemImage: "wifi.exclamationmark")
            } description: {
                Text(message)
            } actions: {
                Button("Retry") {
                    Task { await retry() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding(.top, 10)
    }
}

enum DashboardMonthPickerState {
    static func availableMonths(timelineMonths: [String], selectedMonth: String) -> [String] {
        timelineMonths.isEmpty ? [selectedMonth] : timelineMonths
    }
}

struct EntryDisplayedTag: Equatable, Hashable {
    let key: String
    let name: String
    let color: String?
}

enum EntryTagSelection {
    static func normalizeTagName(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    static func normalize(_ values: [String]) -> [String] {
        var normalized: [String] = []
        var seen = Set<String>()

        for value in values {
            let candidate = normalizeTagName(value)
            guard !candidate.isEmpty, seen.insert(candidate).inserted else { continue }
            normalized.append(candidate)
        }

        return normalized
    }

    static func add(_ value: String, to values: [String]) -> [String] {
        normalize(values + [value])
    }

    static func toggle(_ value: String, in values: [String]) -> [String] {
        let key = normalizeTagName(value)
        guard !key.isEmpty else { return normalize(values) }
        if contains(key, in: values) {
            return remove(key, from: values)
        }
        return add(key, to: values)
    }

    static func remove(_ value: String, from values: [String]) -> [String] {
        let key = normalizeTagName(value)
        return normalize(values.filter { normalizeTagName($0) != key })
    }

    static func contains(_ value: String, in values: [String]) -> Bool {
        let key = normalizeTagName(value)
        return normalize(values).contains(key)
    }

    static func displayTags(tags: [Tag], selected: [String]) -> [EntryDisplayedTag] {
        let catalog = Dictionary(uniqueKeysWithValues: tags.map { (normalizeTagName($0.name), $0) })
        return normalize(selected).map { key in
            let tag = catalog[key]
            return EntryDisplayedTag(
                key: key,
                name: tag?.name ?? key,
                color: tag?.color
            )
        }
    }

    static func filteredOptions(tags: [Tag], selected: [String], query: String) -> [EntryDisplayedTag] {
        let normalizedQuery = normalizeTagName(query)
        var optionsByKey = Dictionary(uniqueKeysWithValues: tags.map {
            (normalizeTagName($0.name), EntryDisplayedTag(key: normalizeTagName($0.name), name: $0.name, color: $0.color))
        })

        for tag in displayTags(tags: tags, selected: selected) {
            optionsByKey[tag.key] = tag
        }

        return optionsByKey.values
            .filter { normalizedQuery.isEmpty || normalizeTagName($0.name).contains(normalizedQuery) }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    static func creatableTagName(tags: [Tag], selected: [String], query: String, allowCreate: Bool) -> String? {
        guard allowCreate else { return nil }
        let candidate = normalizeTagName(query)
        guard !candidate.isEmpty else { return nil }
        let existingNames = Set(tags.map { normalizeTagName($0.name) })
        guard !existingNames.contains(candidate), !contains(candidate, in: selected) else { return nil }
        return candidate
    }
}

private enum FinanceFeedback {
    @MainActor
    static func success() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
    }

    @MainActor
    static func error() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.error)
    }

    @MainActor
    static func destructive() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }
}

private struct EntryTagPickerSheet: View {
    let title: String
    let subtitle: String
    let tags: [Tag]
    @Binding var selection: [String]
    let allowCreate: Bool

    @Environment(\.dismiss) private var dismiss
    @State private var query = ""

    private var displayedTags: [EntryDisplayedTag] {
        EntryTagSelection.filteredOptions(tags: tags, selected: selection, query: query)
    }

    private var creatableTagName: String? {
        EntryTagSelection.creatableTagName(tags: tags, selected: selection, query: query, allowCreate: allowCreate)
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(subtitle)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    TextField("Search tags", text: $query)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                if !selection.isEmpty {
                    Section("Selected") {
                        EntryTagChipGrid(
                            tags: EntryTagSelection.displayTags(tags: tags, selected: selection)
                        ) { tagKey in
                            selection = EntryTagSelection.remove(tagKey, from: selection)
                        }
                    }
                }

                if let creatableTagName {
                    Section("Create") {
                        Button {
                            selection = EntryTagSelection.add(creatableTagName, to: selection)
                            query = ""
                            FinanceFeedback.success()
                        } label: {
                            Label("Create “\(creatableTagName)”", systemImage: "plus.circle.fill")
                        }
                    }
                }

                Section("Available") {
                    if displayedTags.isEmpty {
                        ContentUnavailableView("No matching tags", systemImage: "tag.slash", description: Text("Try a different search term."))
                            .frame(maxWidth: .infinity)
                            .listRowBackground(Color.clear)
                    } else {
                        ForEach(displayedTags, id: \.key) { tag in
                            Button {
                                selection = EntryTagSelection.toggle(tag.key, in: selection)
                            } label: {
                                HStack(spacing: 12) {
                                    EntryTagChip(tag: tag, removable: false)
                                    Spacer()
                                    if EntryTagSelection.contains(tag.key, in: selection) {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(.indigo)
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .navigationTitle(title)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

private struct EntryTagChipGrid: View {
    let tags: [EntryDisplayedTag]
    let onRemove: (String) -> Void

    private let columns = [GridItem(.adaptive(minimum: 104), spacing: 8, alignment: .leading)]

    var body: some View {
        LazyVGrid(columns: columns, alignment: .leading, spacing: 8) {
            ForEach(tags, id: \.key) { tag in
                EntryTagChip(tag: tag) {
                    onRemove(tag.key)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

private struct EntryTagChip: View {
    let tag: EntryDisplayedTag
    let removable: Bool
    let onRemove: (() -> Void)?

    init(tag: EntryDisplayedTag, removable: Bool = true, onRemove: (() -> Void)? = nil) {
        self.tag = tag
        self.removable = removable
        self.onRemove = onRemove
    }

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(dashboardColor(for: tag.color, fallback: .indigo))
                .frame(width: 8, height: 8)
            Text(tag.name)
                .font(.footnote.weight(.semibold))
                .lineLimit(1)
            if removable, let onRemove {
                Button {
                    onRemove()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(
            dashboardColor(for: tag.color, fallback: .indigo).opacity(0.12),
            in: Capsule()
        )
    }
}

private struct DashboardHeroCard: View {
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?

    private var accent: Color {
        dashboardColor(for: selectedFilterGroup?.color, fallback: .indigo)
    }

    private var headlineText: String {
        if let selectedFilterGroup {
            return "\(selectedFilterGroup.name) is driving \(dashboardShareText(selectedFilterGroup.share)) of this month’s spend."
        }
        return "Monthly snapshot for \(FinanceFormatters.monthLabel(for: dashboard.month))."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(FinanceFormatters.monthLabel(for: dashboard.month))
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Text(FinanceFormatters.currency(dashboard.kpis.expenseTotalMinor, currencyCode: dashboard.currencyCode))
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    Text("Expenses recorded")
                        .font(.subheadline.weight(.medium))
                    Text(headlineText)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if let selectedFilterGroup {
                    DashboardContextPill(title: selectedFilterGroup.name, tint: accent)
                }
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                StatPill(
                    title: "Income",
                    value: FinanceFormatters.currency(dashboard.kpis.incomeTotalMinor, currencyCode: dashboard.currencyCode),
                    tint: .green
                )
                StatPill(
                    title: "Net",
                    value: FinanceFormatters.signedCurrency(dashboard.kpis.netTotalMinor, currencyCode: dashboard.currencyCode),
                    tint: dashboard.kpis.netTotalMinor >= 0 ? .green : .orange
                )
                StatPill(
                    title: "Spend Days",
                    value: "\(dashboard.kpis.spendingDays)",
                    tint: accent
                )
                StatPill(
                    title: "Avg Spend Day",
                    value: FinanceFormatters.currency(dashboard.kpis.averageExpenseDayMinor, currencyCode: dashboard.currencyCode),
                    tint: .orange
                )
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            LinearGradient(
                colors: [accent.opacity(0.2), Color(.secondarySystemGroupedBackground)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 26, style: .continuous)
        )
    }
}

private struct DashboardFilterGroupSelector: View {
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?
    @Binding var selectedFilterGroupKey: String?

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Filter groups",
                subtitle: "Use saved classification groups to focus the rest of the dashboard."
            )

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(dashboard.filterGroups, id: \.key) { group in
                        Button {
                            selectedFilterGroupKey = group.key
                        } label: {
                            VStack(alignment: .leading, spacing: 6) {
                                HStack(spacing: 8) {
                                    Circle()
                                        .fill(dashboardColor(for: group.color, fallback: .indigo))
                                        .frame(width: 8, height: 8)
                                    Text(group.name)
                                        .font(.subheadline.weight(.semibold))
                                }
                                Text(FinanceFormatters.currency(group.totalMinor, currencyCode: dashboard.currencyCode))
                                    .font(.caption.monospacedDigit())
                                Text("\(dashboardShareText(group.share)) of expense")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .frame(maxHeight: .infinity, alignment: .leading)
                            .background(
                                group.key == selectedFilterGroup?.key
                                    ? dashboardColor(for: group.color, fallback: .indigo).opacity(0.18)
                                    : Color(.secondarySystemBackground),
                                in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}

private struct DashboardProjectionCard: View {
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?

    private var projectedGroups: [(group: DashboardFilterGroupSummary, totalMinor: Int)] {
        dashboard.filterGroups
            .map { group in
                (group, dashboard.projection.projectedFilterGroupTotals[group.key] ?? 0)
            }
            .sorted { $0.totalMinor > $1.totalMinor }
    }

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Projection",
                subtitle: dashboard.projectionSummary
            )

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 10) {
                StatPill(
                    title: "Spent to Date",
                    value: FinanceFormatters.currency(dashboard.projection.spentToDateMinor, currencyCode: dashboard.currencyCode),
                    tint: .primary
                )
                StatPill(
                    title: "Projected Total",
                    value: dashboard.projection.projectedTotalMinor.map {
                        FinanceFormatters.currency($0, currencyCode: dashboard.currencyCode)
                    } ?? "Not current",
                    tint: .orange
                )
                StatPill(
                    title: "Remaining",
                    value: dashboard.projection.projectedRemainingMinor.map {
                        FinanceFormatters.currency($0, currencyCode: dashboard.currencyCode)
                    } ?? "n/a",
                    tint: .indigo
                )
            }

            if !projectedGroups.isEmpty, dashboard.projection.projectedTotalMinor != nil {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(projectedGroups.prefix(4), id: \.group.key) { item in
                        HStack(spacing: 12) {
                            Circle()
                                .fill(dashboardColor(for: item.group.color, fallback: .indigo))
                                .frame(width: 8, height: 8)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.group.name)
                                    .font(.subheadline.weight(.medium))
                                Text(item.group.key == selectedFilterGroup?.key ? "Currently selected" : "Projected month total")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(FinanceFormatters.currency(item.totalMinor, currencyCode: dashboard.currencyCode))
                                .font(.subheadline.monospacedDigit().weight(.semibold))
                        }
                    }
                }
            }
        }
    }
}

private struct DashboardMonthlyTrendChart: View {
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?
    let tint: Color

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Income vs Expense Trend",
                subtitle: "Income stays in bars while expense stays in the trend line. The selected filter group is overlaid for context."
            )

            Chart(dashboard.monthlyTrend, id: \.month) { point in
                let date = dashboardMonthDate(point.month)

                BarMark(
                    x: .value("Month", date, unit: .month),
                    y: .value("Income", point.incomeTotalMinor)
                )
                .foregroundStyle(Color.green.opacity(0.24))

                if let selectedFilterGroup {
                    AreaMark(
                        x: .value("Month", date, unit: .month),
                        y: .value("Selected", point.filterGroupTotals[selectedFilterGroup.key] ?? 0)
                    )
                    .foregroundStyle(tint.opacity(0.14))

                    LineMark(
                        x: .value("Month", date, unit: .month),
                        y: .value("Selected", point.filterGroupTotals[selectedFilterGroup.key] ?? 0)
                    )
                    .foregroundStyle(tint)
                    .lineStyle(StrokeStyle(lineWidth: 2, dash: [5, 4]))
                }

                LineMark(
                    x: .value("Month", date, unit: .month),
                    y: .value("Expense", point.expenseTotalMinor)
                )
                .foregroundStyle(Color.orange)
                .interpolationMethod(.catmullRom)

                PointMark(
                    x: .value("Month", date, unit: .month),
                    y: .value("Expense", point.expenseTotalMinor)
                )
                .foregroundStyle(Color.orange)
            }
            .frame(height: 260)
            .chartYAxis {
                AxisMarks(position: .leading)
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: min(6, dashboard.monthlyTrend.count))) { value in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [2, 4]))
                        .foregroundStyle(.quaternary)
                    AxisValueLabel(format: .dateTime.month(.abbreviated))
                }
            }

            HStack(spacing: 8) {
                DashboardContextPill(title: "Income", tint: .green)
                DashboardContextPill(title: "Expense", tint: .orange)
                if let selectedFilterGroup {
                    DashboardContextPill(title: selectedFilterGroup.name, tint: tint)
                }
            }
        }
    }
}

private struct DashboardDailyChart: View {
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?
    let tint: Color

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Daily Spending",
                subtitle: selectedFilterGroup.map {
                    "Daily expense bars with a \(String($0.name.lowercased())) overlay."
                } ?? "Daily expense bars for the selected month."
            )

            Chart(dashboard.dailySpending, id: \.date) { point in
                let date = dashboardDayDate(point.date)

                BarMark(
                    x: .value("Day", date, unit: .day),
                    y: .value("Expense", point.expenseTotalMinor)
                )
                .foregroundStyle(Color.orange.opacity(0.3))

                if let selectedFilterGroup {
                    AreaMark(
                        x: .value("Day", date, unit: .day),
                        y: .value("Selected", point.filterGroupTotals[selectedFilterGroup.key] ?? 0)
                    )
                    .foregroundStyle(tint.opacity(0.18))

                    LineMark(
                        x: .value("Day", date, unit: .day),
                        y: .value("Selected", point.filterGroupTotals[selectedFilterGroup.key] ?? 0)
                    )
                    .foregroundStyle(tint)
                    .interpolationMethod(.catmullRom)
                }
            }
            .frame(height: 260)
            .chartYAxis {
                AxisMarks(position: .leading)
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: min(7, dashboard.dailySpending.count))) { value in
                    AxisValueLabel(format: .dateTime.day(.defaultDigits))
                }
            }

            HStack(spacing: 8) {
                StatPill(
                    title: "Median",
                    value: FinanceFormatters.currency(dashboard.kpis.medianExpenseDayMinor, currencyCode: dashboard.currencyCode),
                    tint: .purple
                )
                StatPill(
                    title: "Tracked Groups",
                    value: "\(dashboard.filterGroups.count)",
                    tint: tint
                )
            }
        }
    }
}

private struct DashboardFilterGroupDistributionChart: View {
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?
    let tint: Color

    private var groups: [DashboardFilterGroupSummary] {
        dashboard.filterGroups.sorted { $0.totalMinor > $1.totalMinor }
    }

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Expense by Filter Group",
                subtitle: "Saved classification groups are plotted directly from the current month payload."
            )

            Chart(groups, id: \.key) { group in
                BarMark(
                    x: .value("Spend", group.totalMinor),
                    y: .value("Group", group.name)
                )
                .foregroundStyle(group.key == selectedFilterGroup?.key ? tint : dashboardColor(for: group.color, fallback: .indigo))
            }
            .frame(height: max(220, CGFloat(groups.count) * 42))
            .chartYAxis {
                AxisMarks(position: .leading)
            }

            if let selectedFilterGroup {
                DashboardDeltaPill(
                    title: "Selected group",
                    value: FinanceFormatters.currency(selectedFilterGroup.totalMinor, currencyCode: dashboard.currencyCode),
                    subtitle: dashboardShareText(selectedFilterGroup.share),
                    tint: tint
                )
            }
        }
    }
}

private struct DashboardBreakdownsSection: View {
    let dashboard: Dashboard

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if !dashboard.spendingByTo.isEmpty {
                DashboardBreakdownBarCard(
                    title: "Spending by Destination",
                    subtitle: "Where the money landed this month.",
                    items: dashboard.spendingByTo,
                    currencyCode: dashboard.currencyCode,
                    tint: .indigo
                )
            }

            if !dashboard.spendingByFrom.isEmpty {
                DashboardBreakdownBarCard(
                    title: "Spending by Source",
                    subtitle: "Where expense rows were funded from.",
                    items: dashboard.spendingByFrom,
                    currencyCode: dashboard.currencyCode,
                    tint: .teal
                )
            }

            if !dashboard.spendingByTag.isEmpty {
                DashboardBreakdownBarCard(
                    title: "Spending by Tag",
                    subtitle: "Tag labels that currently explain the most spend.",
                    items: dashboard.spendingByTag,
                    currencyCode: dashboard.currencyCode,
                    tint: .pink
                )
            }
        }
    }
}

private struct DashboardBreakdownBarCard: View {
    let title: String
    let subtitle: String
    let items: [DashboardBreakdownItem]
    let currencyCode: String
    let tint: Color

    private var displayItems: [DashboardBreakdownItem] {
        Array(items.prefix(6))
    }

    var body: some View {
        FeatureCard {
            DashboardSectionLead(title: title, subtitle: subtitle)

            Chart(displayItems, id: \.label) { item in
                BarMark(
                    x: .value("Total", item.totalMinor),
                    y: .value("Label", item.label)
                )
                .foregroundStyle(tint.gradient)
            }
            .frame(height: max(220, CGFloat(displayItems.count) * 40))
            .chartYAxis {
                AxisMarks(position: .leading)
            }

            VStack(alignment: .leading, spacing: 8) {
                ForEach(displayItems, id: \.label) { item in
                    HStack(spacing: 10) {
                        Text(item.label)
                            .font(.footnote.weight(.medium))
                            .lineLimit(1)
                        Spacer()
                        Text(FinanceFormatters.currency(item.totalMinor, currencyCode: currencyCode))
                            .font(.footnote.monospacedDigit())
                        Text(dashboardShareText(item.share))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}

private struct DashboardWeekdayChart: View {
    let dashboard: Dashboard

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Weekday Pattern",
                subtitle: "Use this to spot recurring high-spend days in the month."
            )

            Chart(dashboard.weekdaySpending, id: \.weekday) { point in
                BarMark(
                    x: .value("Weekday", point.weekday),
                    y: .value("Spend", point.totalMinor)
                )
                .foregroundStyle(Color.blue.gradient)
            }
            .frame(height: 220)
            .chartYAxis {
                AxisMarks(position: .leading)
            }
        }
    }
}

private struct DashboardLargestExpensesCard: View {
    let expenses: [DashboardLargestExpenseItem]
    let dashboard: Dashboard
    let selectedFilterGroup: DashboardFilterGroupSummary?
    let tint: Color

    private var matchingGroupNames: [String: String] {
        Dictionary(uniqueKeysWithValues: dashboard.filterGroups.map { ($0.key, $0.name) })
    }

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Largest Expenses",
                subtitle: selectedFilterGroup.map {
                    "Showing the largest rows that match \($0.name)."
                } ?? "Largest individual expense rows for the selected month."
            )

            ForEach(expenses.prefix(5), id: \.id) { expense in
                VStack(alignment: .leading, spacing: 10) {
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(expense.name)
                                .font(.subheadline.weight(.semibold))
                            Text(expense.toEntity ?? "No destination label")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 4) {
                            Text(FinanceFormatters.currency(expense.amountMinor, currencyCode: dashboard.currencyCode))
                                .font(.subheadline.monospacedDigit().weight(.semibold))
                            Text(FinanceFormatters.dayLabel(for: expense.occurredAt))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    if !expense.matchingFilterGroupKeys.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(expense.matchingFilterGroupKeys, id: \.self) { key in
                                    DashboardContextPill(
                                        title: matchingGroupNames[key] ?? key,
                                        tint: key == selectedFilterGroup?.key ? tint : .indigo
                                    )
                                }
                            }
                        }
                    }
                }
                .padding(14)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
        }
    }
}

private struct DashboardReconciliationCard: View {
    let apiClient: APIClient
    let accounts: [DashboardReconciliation]

    var body: some View {
        FeatureCard {
            DashboardSectionLead(
                title: "Reconciliation",
                subtitle: "Account drill-ins stay live so you can inspect snapshots and interval deltas directly from the dashboard."
            )

            ForEach(accounts, id: \.accountId) { account in
                NavigationLink {
                    AccountDetailView(apiClient: apiClient, accountID: account.accountId)
                } label: {
                    DashboardAccountRow(account: account)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

private struct DashboardSectionLead: View {
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

private struct DashboardContextPill: View {
    let title: String
    let tint: Color

    var body: some View {
        Text(title)
            .font(.caption.weight(.semibold))
            .foregroundStyle(tint)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(tint.opacity(0.12), in: Capsule())
    }
}

private struct DashboardDeltaPill: View {
    let title: String
    let value: String
    let subtitle: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline.monospacedDigit().weight(.semibold))
                .foregroundStyle(tint)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(12)
        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

private func dashboardMonthDate(_ value: String) -> Date {
    FinanceFormatters.dayInputFormatter.date(from: "\(value)-01") ?? .now
}

private func dashboardDayDate(_ value: String) -> Date {
    FinanceFormatters.dayInputFormatter.date(from: value) ?? .now
}

private func dashboardShareText(_ share: Double) -> String {
    "\(Int((share * 100).rounded()))%"
}

private func dashboardColor(for hex: String?, fallback: Color) -> Color {
    guard let hex else { return fallback }
    let normalized = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
    guard normalized.count == 6 || normalized.count == 8 else { return fallback }

    var value: UInt64 = 0
    guard Scanner(string: normalized).scanHexInt64(&value) else { return fallback }

    let red: Double
    let green: Double
    let blue: Double
    let alpha: Double

    if normalized.count == 8 {
        red = Double((value & 0xFF00_0000) >> 24) / 255
        green = Double((value & 0x00FF_0000) >> 16) / 255
        blue = Double((value & 0x0000_FF00) >> 8) / 255
        alpha = Double(value & 0x0000_00FF) / 255
    } else {
        red = Double((value & 0xFF00_00) >> 16) / 255
        green = Double((value & 0x00FF_00) >> 8) / 255
        blue = Double(value & 0x0000_FF) / 255
        alpha = 1
    }

    return Color(.sRGB, red: red, green: green, blue: blue, opacity: alpha)
}

private extension Dashboard {
    var hasDisplayContent: Bool {
        kpis.expenseTotalMinor != 0
            || kpis.incomeTotalMinor != 0
            || !largestExpenses.isEmpty
            || !reconciliation.isEmpty
    }

    var projectionSummary: String {
        if let projectedTotalMinor = projection.projectedTotalMinor {
            return "Projected month-end spend is \(FinanceFormatters.currency(projectedTotalMinor, currencyCode: currencyCode)) with \(projection.daysRemaining) day\(projection.daysRemaining == 1 ? "" : "s") remaining."
        }
        return "No month-end projection is available yet."
    }
}

private extension EntryKind {
    var displayName: String {
        switch self {
        case .expense:
            return "Expense"
        case .income:
            return "Income"
        case .transfer:
            return "Transfer"
        }
    }

    var symbolName: String {
        switch self {
        case .expense:
            return "arrow.up.forward.circle.fill"
        case .income:
            return "arrow.down.forward.circle.fill"
        case .transfer:
            return "arrow.left.arrow.right.circle.fill"
        }
    }

    var tintColor: Color {
        switch self {
        case .expense:
            return .orange
        case .income:
            return .green
        case .transfer:
            return .blue
        }
    }
}

private extension Entry {
    var counterpartySummary: String {
        let from = fromEntity ?? "Unspecified source"
        let to = toEntity ?? "Unspecified destination"
        return "\(from) → \(to)"
    }

    var tagSummary: String? {
        guard !tags.isEmpty else { return nil }
        return tags.map(\.name).joined(separator: ", ")
    }
}

private extension String {
    var emptyAsNil: String? {
        let normalized = trimmingCharacters(in: .whitespacesAndNewlines)
        return normalized.isEmpty ? nil : normalized
    }
}
