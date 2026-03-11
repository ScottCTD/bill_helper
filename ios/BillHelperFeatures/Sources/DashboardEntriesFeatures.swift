import Charts
import SwiftUI

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
            if selectedFilterGroupKey == nil {
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
    @StateObject private var model: DashboardScreenModel
    @Binding private var deepLink: AppDeepLink?

    init(apiClient: APIClient, deepLink: Binding<AppDeepLink?>) {
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
                        dashboard: dashboard,
                        timelineMonths: model.timelineMonths,
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
                }
            }
        }
    }
}

private struct DashboardLoadedView: View {
    let dashboard: Dashboard
    let timelineMonths: [String]
    @Binding var selectedFilterGroupKey: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            FeatureCard {
                VStack(alignment: .leading, spacing: 12) {
                    Text(FinanceFormatters.monthLabel(for: dashboard.month))
                        .font(.title2.weight(.bold))
                    Text(dashboard.projectionSummary)
                        .foregroundStyle(.secondary)

                    HStack {
                        StatPill(title: "Spend", value: FinanceFormatters.currency(dashboard.kpis.expenseTotalMinor, currencyCode: dashboard.currencyCode), tint: .orange)
                        StatPill(title: "Net", value: FinanceFormatters.signedCurrency(dashboard.kpis.netTotalMinor, currencyCode: dashboard.currencyCode), tint: dashboard.kpis.netTotalMinor >= 0 ? .green : .red)
                    }
                }
            }

            if !dashboard.filterGroups.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Filter groups")
                            .font(.headline)
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 10) {
                                ForEach(dashboard.filterGroups, id: \.key) { group in
                                    Button {
                                        selectedFilterGroupKey = group.key
                                    } label: {
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(group.name)
                                            Text(FinanceFormatters.currency(group.totalMinor, currencyCode: dashboard.currencyCode))
                                                .font(.caption)
                                        }
                                        .font(.subheadline.weight(.semibold))
                                        .padding(.horizontal, 12)
                                        .padding(.vertical, 10)
                                        .background(group.key == selectedFilterGroupKey ? Color.indigo.opacity(0.14) : Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                    }
                }
            }

            if !dashboard.dailySpending.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Daily spending")
                            .font(.headline)
                        Chart(dashboard.dailySpending, id: \.date) { point in
                            BarMark(
                                x: .value("Day", FinanceFormatters.dayLabel(for: point.date)),
                                y: .value("Expense", point.expenseTotalMinor)
                            )
                            .foregroundStyle(Color.indigo.gradient)
                        }
                        .frame(height: 180)
                    }
                }
            }

            if !dashboard.monthlyTrend.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Monthly trend")
                            .font(.headline)
                        Chart(dashboard.monthlyTrend, id: \.month) { point in
                            LineMark(
                                x: .value("Month", FinanceFormatters.monthLabel(for: point.month)),
                                y: .value("Expense", point.expenseTotalMinor)
                            )
                            .foregroundStyle(Color.orange.gradient)
                        }
                        .frame(height: 180)
                    }
                }
            }

            if !dashboard.largestExpenses.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Largest expenses")
                            .font(.headline)
                        ForEach(dashboard.largestExpenses, id: \.id) { expense in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(expense.name)
                                        .font(.subheadline.weight(.semibold))
                                    Spacer()
                                    Text(FinanceFormatters.currency(expense.amountMinor, currencyCode: dashboard.currencyCode))
                                        .font(.subheadline.monospacedDigit())
                                }
                                Text(expense.toEntity ?? "Unspecified destination")
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            }

            if !dashboard.reconciliation.isEmpty {
                FeatureCard {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Accounts")
                            .font(.headline)
                        ForEach(dashboard.reconciliation, id: \.accountId) { account in
                            NavigationLink {
                                AccountDetailView(apiClient: APIClient(baseURL: URL(string: "http://localhost")!))
                            } label: {
                                DashboardAccountRow(account: account, currencyCode: dashboard.currencyCode)
                            }
                            .disabled(true)
                        }
                    }
                }
            }
        }
    }
}

private struct DashboardAccountRow: View {
    let account: DashboardReconciliation
    let currencyCode: String

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(account.accountName)
                    .font(.subheadline.weight(.semibold))
                Text(account.latestSnapshotAt.map { "Snapshot \($0)" } ?? "No snapshots yet")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(FinanceFormatters.signedCurrency(account.currentTrackedChangeMinor ?? 0, currencyCode: currencyCode))
                    .font(.subheadline.monospacedDigit())
                Text("\(account.mismatchedIntervalCount) mismatches")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
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
    @State private var selectedTagName: String?
    @State private var selectedCurrencyCode: String?
    @State private var selectedSource = ""
    @State private var selectedFilterGroupID: String?
    @State private var editorMode: EntryEditorMode?
    @State private var deletionTarget: Entry?
    @State private var path: [String] = []
    @State private var editorError: String?

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
            .alert("Delete entry?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
                Button("Delete", role: .destructive) {
                    guard let target = deletionTarget else { return }
                    Task {
                        do {
                            try await model.deleteEntry(id: target.id)
                        } catch {
                            editorError = error.localizedDescription
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

            Picker("Tag", selection: Binding(get: { selectedTagName }, set: { selectedTagName = $0 })) {
                Text("All").tag(String?.none)
                ForEach(model.tags.map(\.name), id: \.self) { name in
                    Text(name).tag(Optional(name))
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
        }
    }

    private func filteredEntries(from entries: [Entry]) -> [Entry] {
        entries.filter { entry in
            if !searchText.isEmpty {
                let haystack = [entry.name, entry.fromEntity ?? "", entry.toEntity ?? "", entry.owner ?? ""]
                    .joined(separator: " ")
                    .lowercased()
                guard haystack.contains(searchText.lowercased()) else { return false }
            }
            if let selectedKind, entry.kind != selectedKind {
                return false
            }
            if let selectedTagName, !entry.tags.contains(where: { $0.name == selectedTagName }) {
                return false
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
                            Text(entry.tags.map(\.name).joined(separator: ", "))
                        }
                    }
                    if let notes = entry.markdownBody, !notes.isEmpty {
                        Section("Notes") {
                            Text(notes)
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
    @State private var occurredAt: String = DashboardScreenModel.defaultMonthString().appending("-01")
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
    @State private var selectedTags = Set<String>()
    @State private var directGroupID = ""
    @State private var directGroupRole: GroupMemberRole = .child
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Entry") {
                    Picker("Kind", selection: $kind) {
                        ForEach(EntryKind.allCases, id: \.self) { kind in
                            Text(kind.displayName).tag(kind)
                        }
                    }
                    TextField("Occurred at", text: $occurredAt)
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
                    }
                }

                Section("Tags") {
                    ForEach(model.tags, id: \.name) { tag in
                        Toggle(tag.name, isOn: Binding(
                            get: { selectedTags.contains(tag.name) },
                            set: { isSelected in
                                if isSelected {
                                    selectedTags.insert(tag.name)
                                } else {
                                    selectedTags.remove(tag.name)
                                }
                            }
                        ))
                    }
                }

                Section("Notes") {
                    TextEditor(text: $markdownBody)
                        .frame(minHeight: 120)
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
            .onAppear(perform: populateIfNeeded)
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
        guard case .edit(let entry) = mode else { return }
        kind = entry.kind
        occurredAt = entry.occurredAt
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
        selectedTags = Set(entry.tags.map(\.name))
        directGroupID = entry.directGroup?.id ?? ""
        directGroupRole = entry.directGroupMemberRole ?? .child
    }

    private func save() async {
        let amountMinor = Int(((Double(amountMajor) ?? 0) * 100).rounded())
        guard amountMinor > 0 else {
            errorMessage = "Enter a valid amount."
            return
        }

        if selectedGroup?.groupType == .split && directGroupID.isEmpty == false && selectedGroup != nil {
            // valid path, keep chosen role
        }

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
                        name: name,
                        amountMinor: amountMinor,
                        currencyCode: currencyCode,
                        fromEntityId: fromEntityID.isEmpty ? nil : fromEntityID,
                        toEntityId: toEntityID.isEmpty ? nil : toEntityID,
                        ownerUserId: ownerUserID.isEmpty ? nil : ownerUserID,
                        fromEntity: fromEntityText.emptyAsNil,
                        toEntity: toEntityText.emptyAsNil,
                        owner: ownerText.emptyAsNil,
                        markdownBody: markdownBody.emptyAsNil,
                        tags: Array(selectedTags).sorted(),
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
                        name: name,
                        amountMinor: amountMinor,
                        currencyCode: currencyCode,
                        fromEntityId: fromEntityID.emptyAsNil,
                        toEntityId: toEntityID.emptyAsNil,
                        ownerUserId: ownerUserID.emptyAsNil,
                        fromEntity: fromEntityText.emptyAsNil,
                        toEntity: toEntityText.emptyAsNil,
                        owner: ownerText.emptyAsNil,
                        markdownBody: markdownBody.emptyAsNil,
                        tags: Array(selectedTags).sorted(),
                        directGroupId: directGroupID.emptyAsNil,
                        directGroupMemberRole: selectedGroup?.groupType == .split ? directGroupRole : nil
                    )
                )
            }
            errorMessage = nil
            onDismiss()
        } catch {
            errorMessage = error.localizedDescription
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
