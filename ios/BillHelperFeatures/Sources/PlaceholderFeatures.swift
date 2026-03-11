import SwiftUI

enum ManageRoute: Hashable, Identifiable {
    case accounts
    case entities
    case tags
    case groups
    case filterGroups
    case taxonomies
    case currencies
    case users
    case account(String)
    case group(String)

    var id: String {
        switch self {
        case .accounts:
            return "accounts"
        case .entities:
            return "entities"
        case .tags:
            return "tags"
        case .groups:
            return "groups"
        case .filterGroups:
            return "filter-groups"
        case .taxonomies:
            return "taxonomies"
        case .currencies:
            return "currencies"
        case .users:
            return "users"
        case .account(let id):
            return "account-\(id)"
        case .group(let id):
            return "group-\(id)"
        }
    }
}

@MainActor
final class ManagePermissionsModel: ObservableObject {
    @Published private(set) var currentUser: User?
    @Published private(set) var errorMessage: String?

    private let apiClient: APIClient
    private var hasLoaded = false

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    var isAdmin: Bool {
        currentUser?.isAdmin ?? false
    }

    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        await reload()
    }

    func reload() async {
        do {
            currentUser = try await apiClient.listUsers().first(where: \.isCurrentUser)
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct ManageRootView: View {
    let apiClient: APIClient
    @Binding var deepLink: AppDeepLink?
    @StateObject private var permissionsModel: ManagePermissionsModel
    @State private var selectedRoute: ManageRoute?

    init(apiClient: APIClient, deepLink: Binding<AppDeepLink?>) {
        self.apiClient = apiClient
        _deepLink = deepLink
        _permissionsModel = StateObject(wrappedValue: ManagePermissionsModel(apiClient: apiClient))
    }

    var body: some View {
        List {
            if let errorMessage = permissionsModel.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            Section("Core") {
                manageButton("Accounts", subtitle: "Balances, snapshots, reconciliation, and ownership", symbol: "creditcard", route: .accounts)
                manageButton("Groups", subtitle: "Bundle, split, and recurring groups", symbol: "square.grid.2x2", route: .groups)
                manageButton("Filter Groups", subtitle: "Saved dashboard and entry filters", symbol: "line.3.horizontal.decrease.circle", route: .filterGroups)
            }

            Section("Catalogs") {
                manageButton("Entities", subtitle: permissionsModel.isAdmin ? "Create and manage counterparties" : "Browse visible counterparties", symbol: "building.2", route: .entities)
                manageButton("Tags", subtitle: permissionsModel.isAdmin ? "Create and manage tags" : "Browse visible tags", symbol: "tag", route: .tags)
                manageButton("Taxonomies", subtitle: "Browse and edit taxonomy terms", symbol: "list.bullet.indent", route: .taxonomies)
                manageButton("Currencies", subtitle: "Read-only discovered and built-in currencies", symbol: "banknote", route: .currencies)
                manageButton("Users", subtitle: permissionsModel.isAdmin ? "Create and manage users" : "Inspect and edit your own user", symbol: "person.2", route: .users)
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color(.systemGroupedBackground))
        .navigationDestination(item: $selectedRoute) { route in
            switch route {
            case .accounts:
                AccountsWorkspaceView(apiClient: apiClient, canEdit: true)
            case .entities:
                EntitiesWorkspaceView(apiClient: apiClient, canEdit: permissionsModel.isAdmin)
            case .tags:
                TagsWorkspaceView(apiClient: apiClient, canEdit: permissionsModel.isAdmin)
            case .groups:
                GroupsWorkspaceView(apiClient: apiClient, canEdit: true)
            case .filterGroups:
                FilterGroupsWorkspaceView(apiClient: apiClient)
            case .taxonomies:
                TaxonomiesWorkspaceView(apiClient: apiClient, canEdit: permissionsModel.isAdmin)
            case .currencies:
                CurrenciesWorkspaceView(apiClient: apiClient)
            case .users:
                UsersWorkspaceView(apiClient: apiClient, canEdit: permissionsModel.isAdmin)
            case .account(let id):
                AccountDetailView(apiClient: apiClient, accountID: id)
            case .group(let id):
                GroupDetailView(apiClient: apiClient, groupID: id, canEdit: true)
            }
        }
        .task { await permissionsModel.loadIfNeeded() }
        .onChange(of: deepLink) { _, newValue in
            switch newValue {
            case .account(let id)?:
                selectedRoute = .account(id)
                deepLink = nil
            case .group(let id)?:
                selectedRoute = .group(id)
                deepLink = nil
            default:
                break
            }
        }
    }

    private func manageButton(_ title: String, subtitle: String, symbol: String, route: ManageRoute) -> some View {
        Button {
            selectedRoute = route
        } label: {
            HStack(spacing: 14) {
                Image(systemName: symbol)
                    .frame(width: 28, height: 28)
                    .foregroundStyle(.indigo)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.body.weight(.semibold))
                        .foregroundStyle(.primary)
                    Text(subtitle)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
            .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
    }
}

struct SettingsRootView: View {
    @ObservedObject var composition: AppComposition
    @State private var baseURL = ""
    @State private var principalName = ""
    @State private var runtimeSettings: RuntimeSettings?
    @State private var currentUser: User?
    @State private var currencies: [Currency] = []
    @State private var errorMessage: String?
    @State private var isSavingConnection = false
    @State private var isSavingSettings = false
    @State private var userMemoryText = ""
    @State private var availableModelsText = ""
    @State private var settingsForm = RuntimeSettingsUpdatePayload()

    private var canEditSettings: Bool {
        currentUser?.isAdmin ?? false
    }

    private var availableCurrencyCodes: [String] {
        var seen = Set<String>()
        let candidates = currencies.map(\.code)
            + [runtimeSettings?.defaultCurrencyCode, runtimeSettings?.dashboardCurrencyCode].compactMap { $0 }
        return candidates.filter { seen.insert($0).inserted }
    }

    private var availableModelOptions: [String] {
        var seen = Set<String>()
        let candidates = (runtimeSettings?.availableAgentModels ?? [])
            + [runtimeSettings?.agentModel].compactMap { $0 }
        return candidates.filter { seen.insert($0).inserted }
    }

    var body: some View {
        List {
            Section("Session") {
                TextField("Backend URL", text: $baseURL)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()
                TextField("Principal name", text: $principalName)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button(isSavingConnection ? "Reconnecting…" : "Save and reconnect") {
                    Task {
                        isSavingConnection = true
                        await composition.updateConnection(baseURLString: baseURL, principalName: principalName)
                        isSavingConnection = false
                        await load()
                    }
                }
                .disabled(isSavingConnection || baseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || principalName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                Button("Sign out", role: .destructive) {
                    composition.signOut()
                }
            }

            if let runtimeSettings {
                Section("Runtime Settings") {
                    Picker("Default currency", selection: Binding(
                        get: { settingsForm.defaultCurrencyCode ?? runtimeSettings.defaultCurrencyCode },
                        set: { settingsForm.defaultCurrencyCode = $0 }
                    )) {
                        ForEach(availableCurrencyCodes, id: \.self) { code in
                            Text(code).tag(code)
                        }
                    }
                    .pickerStyle(.menu)

                    Picker("Dashboard currency", selection: Binding(
                        get: { settingsForm.dashboardCurrencyCode ?? runtimeSettings.dashboardCurrencyCode },
                        set: { settingsForm.dashboardCurrencyCode = $0 }
                    )) {
                        ForEach(availableCurrencyCodes, id: \.self) { code in
                            Text(code).tag(code)
                        }
                    }
                    .pickerStyle(.menu)

                    Picker("Agent model", selection: Binding(
                        get: { settingsForm.agentModel ?? runtimeSettings.agentModel },
                        set: { settingsForm.agentModel = normalizedOptional($0) }
                    )) {
                        ForEach(availableModelOptions, id: \.self) { model in
                            Text(model).tag(model)
                        }
                    }
                    .pickerStyle(.menu)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Available agent models")
                            .font(.subheadline.weight(.semibold))
                        TextField("One model per line", text: $availableModelsText, axis: .vertical)
                            .lineLimit(2 ... 8)
                            .textFieldStyle(.roundedBorder)
                            .disabled(!canEditSettings)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("User memory")
                            .font(.subheadline.weight(.semibold))
                        TextField("One memory item per line", text: $userMemoryText, axis: .vertical)
                            .lineLimit(2 ... 8)
                            .textFieldStyle(.roundedBorder)
                            .disabled(!canEditSettings)
                    }

                    LabeledContent("Max steps") {
                        TextField("Max steps", value: Binding(
                            get: { settingsForm.agentMaxSteps ?? runtimeSettings.agentMaxSteps },
                            set: { settingsForm.agentMaxSteps = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.numberPad)
                    }

                    LabeledContent("Bulk concurrent threads") {
                        TextField("Bulk concurrent threads", value: Binding(
                            get: { settingsForm.agentBulkMaxConcurrentThreads ?? runtimeSettings.agentBulkMaxConcurrentThreads },
                            set: { settingsForm.agentBulkMaxConcurrentThreads = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.numberPad)
                    }

                    LabeledContent("Retry max attempts") {
                        TextField("Retry max attempts", value: Binding(
                            get: { settingsForm.agentRetryMaxAttempts ?? runtimeSettings.agentRetryMaxAttempts },
                            set: { settingsForm.agentRetryMaxAttempts = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.numberPad)
                    }

                    LabeledContent("Retry initial wait") {
                        TextField("Retry initial wait", value: Binding(
                            get: { settingsForm.agentRetryInitialWaitSeconds ?? runtimeSettings.agentRetryInitialWaitSeconds },
                            set: { settingsForm.agentRetryInitialWaitSeconds = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.decimalPad)
                    }

                    LabeledContent("Retry max wait") {
                        TextField("Retry max wait", value: Binding(
                            get: { settingsForm.agentRetryMaxWaitSeconds ?? runtimeSettings.agentRetryMaxWaitSeconds },
                            set: { settingsForm.agentRetryMaxWaitSeconds = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.decimalPad)
                    }

                    LabeledContent("Retry backoff") {
                        TextField("Retry backoff", value: Binding(
                            get: { settingsForm.agentRetryBackoffMultiplier ?? runtimeSettings.agentRetryBackoffMultiplier },
                            set: { settingsForm.agentRetryBackoffMultiplier = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.decimalPad)
                    }

                    LabeledContent("Image max bytes") {
                        TextField("Image max bytes", value: Binding(
                            get: { settingsForm.agentMaxImageSizeBytes ?? runtimeSettings.agentMaxImageSizeBytes },
                            set: { settingsForm.agentMaxImageSizeBytes = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.numberPad)
                    }

                    LabeledContent("Images per message") {
                        TextField("Images per message", value: Binding(
                            get: { settingsForm.agentMaxImagesPerMessage ?? runtimeSettings.agentMaxImagesPerMessage },
                            set: { settingsForm.agentMaxImagesPerMessage = $0 }
                        ), format: .number)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.numberPad)
                    }

                    LabeledContent("Agent base URL") {
                        TextField("Agent base URL", text: Binding(
                            get: { settingsForm.agentBaseURL ?? runtimeSettings.agentBaseURL ?? "" },
                            set: { settingsForm.agentBaseURL = normalizedOptional($0) }
                        ))
                        .multilineTextAlignment(.trailing)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                    }

                    Button(isSavingSettings ? "Saving…" : "Save runtime settings") {
                        Task { await saveRuntimeSettings() }
                    }
                    .disabled(isSavingSettings || !canEditSettings)
                }
                .disabled(!canEditSettings)
            }

            Section("Diagnostics") {
                LabeledContent("Environment", value: composition.configuration.environment.displayName)
                LabeledContent("Current principal", value: currentUser?.name ?? principalName)
                LabeledContent("Admin", value: canEditSettings ? "Yes" : "No")
                LabeledContent("Backend", value: composition.activeAPIBaseURL.absoluteString)
                if let runtimeSettings {
                    LabeledContent("Configured model", value: runtimeSettings.agentModel)
                    LabeledContent("Enabled models", value: "\(runtimeSettings.availableAgentModels.count)")
                    LabeledContent("Image max bytes", value: "\(runtimeSettings.agentMaxImageSizeBytes)")
                    LabeledContent("Images / message", value: "\(runtimeSettings.agentMaxImagesPerMessage)")
                    LabeledContent("Agent key configured", value: runtimeSettings.agentApiKeyConfigured ? "Yes" : "No")
                }
                Button("Refresh diagnostics") {
                    Task { await load() }
                }
            }

            if let errorMessage, !errorMessage.isEmpty {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color(.systemGroupedBackground))
        .task { await load() }
        .navigationTitle("Settings")
        .onAppear {
            baseURL = composition.activeAPIBaseURL.absoluteString
            principalName = composition.sessionStore.currentSession?.currentUserName ?? ""
        }
    }

    private func load() async {
        do {
            async let settingsTask = composition.apiClient.runtimeSettings()
            async let usersTask = composition.apiClient.listUsers()
            async let currenciesTask = composition.apiClient.listCurrencies()
            let loadedSettings = try await settingsTask
            runtimeSettings = loadedSettings
            settingsForm = RuntimeSettingsUpdatePayload()
            currentUser = try await usersTask.first(where: \.isCurrentUser)
            currencies = try await currenciesTask.sorted(by: { $0.code.localizedCaseInsensitiveCompare($1.code) == .orderedAscending })
            availableModelsText = loadedSettings.availableAgentModels.joined(separator: "\n")
            userMemoryText = (loadedSettings.userMemory ?? []).joined(separator: "\n")
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func saveRuntimeSettings() async {
        guard canEditSettings else { return }
        isSavingSettings = true
        defer { isSavingSettings = false }
        do {
            settingsForm.userMemory = lineSeparatedValues(from: userMemoryText)
            settingsForm.availableAgentModels = lineSeparatedValues(from: availableModelsText)
            runtimeSettings = try await composition.apiClient.updateRuntimeSettings(settingsForm)
            settingsForm = RuntimeSettingsUpdatePayload()
            if let runtimeSettings {
                availableModelsText = runtimeSettings.availableAgentModels.joined(separator: "\n")
                userMemoryText = (runtimeSettings.userMemory ?? []).joined(separator: "\n")
            }
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
private final class AccountsWorkspaceModel: ObservableObject {
    @Published private(set) var accounts: [Account] = []
    @Published private(set) var users: [User] = []
    @Published private(set) var currencies: [Currency] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }

        do {
            async let accountsTask = apiClient.listAccounts()
            async let usersTask = apiClient.listUsers()
            async let currenciesTask = apiClient.listCurrencies()
            accounts = try await accountsTask.sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            users = try await usersTask.sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            currencies = try await currenciesTask.sorted(by: { $0.code.localizedCaseInsensitiveCompare($1.code) == .orderedAscending })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(mode: AccountEditorMode, draft: AccountDraft) async throws {
        switch mode {
        case .create:
            _ = try await apiClient.createAccount(
                AccountCreatePayload(
                    ownerUserId: draft.ownerUserId,
                    name: draft.name,
                    markdownBody: draft.markdownBody,
                    currencyCode: draft.currencyCode,
                    isActive: draft.isActive
                )
            )
        case .edit(let account):
            _ = try await apiClient.updateAccount(
                id: account.id,
                payload: AccountUpdatePayload(
                    ownerUserId: draft.ownerUserId,
                    name: draft.name,
                    markdownBody: draft.markdownBody,
                    currencyCode: draft.currencyCode,
                    isActive: draft.isActive
                )
            )
        }
        await reload()
    }

    func delete(account: Account) async throws {
        try await apiClient.deleteAccount(id: account.id)
        await reload()
    }
}

private struct AccountsWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    @StateObject private var model: AccountsWorkspaceModel
    @State private var searchText = ""
    @State private var editorMode: AccountEditorMode?
    @State private var deletionTarget: Account?
    @State private var selectedAccount: Account?

    init(apiClient: APIClient, canEdit: Bool) {
        self.apiClient = apiClient
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: AccountsWorkspaceModel(apiClient: apiClient))
    }

    private var filteredAccounts: [Account] {
        model.accounts.filter { account in
            searchText.isEmpty
                || account.name.localizedCaseInsensitiveContains(searchText)
                || account.currencyCode.localizedCaseInsensitiveContains(searchText)
                || (ownerName(for: account).localizedCaseInsensitiveContains(searchText))
        }
    }

    var body: some View {
        Group {
            if model.isLoading && model.accounts.isEmpty {
                ManageLoadingState(title: "Loading accounts…")
            } else {
                List {
                    if !model.accounts.isEmpty {
                        Section {
                            HStack {
                                ManageMetric(title: "Accounts", value: "\(model.accounts.count)", tint: .indigo)
                                Spacer()
                                ManageMetric(title: "Active", value: "\(model.accounts.filter(\.isActive).count)", tint: .green)
                                Spacer()
                                ManageMetric(title: "Currencies", value: "\(Set(model.accounts.map(\.currencyCode)).count)", tint: .orange)
                            }
                            .listRowInsets(EdgeInsets(top: 10, leading: 16, bottom: 10, trailing: 16))
                        }
                    }

                    if let errorMessage = model.errorMessage {
                        Section {
                            ManageInlineError(message: errorMessage)
                        }
                    }

                    Section("Accounts") {
                        if filteredAccounts.isEmpty {
                            ManageEmptyRow(text: searchText.isEmpty ? "No accounts yet" : "No accounts match the current search")
                        } else {
                            ForEach(filteredAccounts) { account in
                                Button {
                                    selectedAccount = account
                                } label: {
                                    VStack(alignment: .leading, spacing: 6) {
                                        HStack {
                                            Text(account.name)
                                                .font(.body.weight(.semibold))
                                                .foregroundStyle(.primary)
                                            if !account.isActive {
                                                ManageBadge(text: "Inactive", tint: .secondary)
                                            }
                                            Spacer()
                                            Text(account.currencyCode)
                                                .font(.caption.weight(.semibold))
                                                .foregroundStyle(.secondary)
                                        }
                                        Text(ownerName(for: account))
                                            .font(.footnote)
                                            .foregroundStyle(.secondary)
                                        if let markdownBody = account.markdownBody, !markdownBody.isEmpty {
                                            Text(markdownBody)
                                                .font(.caption)
                                                .foregroundStyle(.tertiary)
                                                .lineLimit(2)
                                        }
                                    }
                                    .padding(.vertical, 4)
                                }
                                .buttonStyle(.plain)
                                .swipeActions(edge: .trailing) {
                                    if canEdit {
                                        Button(role: .destructive) {
                                            deletionTarget = account
                                        } label: {
                                            Label("Delete", systemImage: "trash")
                                        }
                                    }
                                }
                                .swipeActions(edge: .leading) {
                                    if canEdit {
                                        Button {
                                            editorMode = .edit(account)
                                        } label: {
                                            Label("Edit", systemImage: "pencil")
                                        }
                                        .tint(.indigo)
                                    }
                                }
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Accounts")
        .searchable(text: $searchText, prompt: "Search accounts")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .toolbar {
            if canEdit {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editorMode = .create
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
        }
        .sheet(item: $editorMode) { mode in
            AccountEditorSheet(
                mode: mode,
                currencies: model.currencies,
                users: model.users
            ) { draft in
                try await model.save(mode: mode, draft: draft)
            }
        }
        .navigationDestination(item: $selectedAccount) { account in
            AccountDetailView(apiClient: apiClient, accountID: account.id)
        }
        .alert("Delete account?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
            Button("Delete", role: .destructive) {
                guard let deletionTarget else { return }
                Task {
                    do {
                        try await model.delete(account: deletionTarget)
                    } catch {
                        model.errorMessage = error.localizedDescription
                    }
                    self.deletionTarget = nil
                }
            }
            Button("Cancel", role: .cancel) {
                deletionTarget = nil
            }
        } message: {
            Text("Accounts can only be deleted when the backend accepts the request.")
        }
    }

    private func ownerName(for account: Account) -> String {
        model.users.first(where: { $0.id == account.ownerUserId })?.name ?? "Shared or unassigned"
    }
}

private enum AccountEditorMode: Identifiable {
    case create
    case edit(Account)

    var id: String {
        switch self {
        case .create:
            return "create-account"
        case .edit(let account):
            return "edit-account-\(account.id)"
        }
    }
}

private struct AccountDraft {
    var ownerUserId: String?
    var name: String
    var markdownBody: String?
    var currencyCode: String
    var isActive: Bool

    init(account: Account? = nil, fallbackCurrency: String) {
        ownerUserId = account?.ownerUserId
        name = account?.name ?? ""
        markdownBody = account?.markdownBody
        currencyCode = account?.currencyCode ?? fallbackCurrency
        isActive = account?.isActive ?? true
    }
}

private struct AccountEditorSheet: View {
    let mode: AccountEditorMode
    let currencies: [Currency]
    let users: [User]
    let onSave: (AccountDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var draft: AccountDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(mode: AccountEditorMode, currencies: [Currency], users: [User], onSave: @escaping (AccountDraft) async throws -> Void) {
        self.mode = mode
        self.currencies = currencies
        self.users = users
        self.onSave = onSave
        let existingAccount: Account?
        switch mode {
        case .create:
            existingAccount = nil
        case .edit(let account):
            existingAccount = account
        }
        _draft = State(initialValue: AccountDraft(account: existingAccount, fallbackCurrency: currencies.first?.code ?? "CAD"))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Name", text: $draft.name)
                    Picker("Currency", selection: Binding(
                        get: { draft.currencyCode },
                        set: { draft.currencyCode = $0 }
                    )) {
                        ForEach(currencies, id: \.code) { currency in
                            Text("\(currency.code) · \(currency.name)").tag(currency.code)
                        }
                    }
                    Picker("Owner", selection: Binding(
                        get: { draft.ownerUserId ?? "" },
                        set: { draft.ownerUserId = normalizedOptional($0) }
                    )) {
                        Text("Shared / none").tag("")
                        ForEach(users) { user in
                            Text(user.name).tag(user.id)
                        }
                    }
                    Toggle("Active", isOn: $draft.isActive)
                }

                Section("Notes") {
                    TextField("Markdown notes", text: Binding(
                        get: { draft.markdownBody ?? "" },
                        set: { draft.markdownBody = normalizedOptional($0) }
                    ), axis: .vertical)
                    .lineLimit(3 ... 8)
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New Account"
        case .edit:
            return "Edit Account"
        }
    }

    private func save() async {
        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !draft.name.isEmpty else {
            errorMessage = "Account name is required."
            return
        }
        guard !draft.currencyCode.isEmpty else {
            errorMessage = "Choose a currency."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(draft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
private final class EntitiesWorkspaceModel: ObservableObject {
    @Published private(set) var entities: [Entity] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }
        do {
            entities = try await apiClient.listEntities().sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(mode: EntityEditorMode, draft: EntityDraft) async throws {
        switch mode {
        case .create:
            _ = try await apiClient.createEntity(EntityCreatePayload(name: draft.name, category: draft.category))
        case .edit(let entity):
            _ = try await apiClient.updateEntity(id: entity.id, payload: EntityUpdatePayload(name: draft.name, category: draft.category))
        }
        await reload()
    }

    func delete(entity: Entity) async throws {
        try await apiClient.deleteEntity(id: entity.id)
        await reload()
    }
}

private struct EntitiesWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    @StateObject private var model: EntitiesWorkspaceModel
    @State private var searchText = ""
    @State private var editorMode: EntityEditorMode?
    @State private var deletionTarget: Entity?

    init(apiClient: APIClient, canEdit: Bool) {
        self.apiClient = apiClient
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: EntitiesWorkspaceModel(apiClient: apiClient))
    }

    private var filteredEntities: [Entity] {
        model.entities.filter { entity in
            searchText.isEmpty
                || entity.name.localizedCaseInsensitiveContains(searchText)
                || (entity.category ?? "").localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        List {
            if !canEdit {
                Section {
                    ManageReadOnlyNote(text: "Entity edits require an admin principal. Visible entities remain searchable here.")
                }
            }

            if let errorMessage = model.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            Section("Entities") {
                if filteredEntities.isEmpty {
                    ManageEmptyRow(text: searchText.isEmpty ? "No entities available" : "No entities match the current search")
                } else {
                    ForEach(filteredEntities) { entity in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(entity.name)
                                    .font(.body.weight(.semibold))
                                if entity.isAccount {
                                    ManageBadge(text: "Account-backed", tint: .secondary)
                                }
                                Spacer()
                                if let entryCount = entity.entryCount {
                                    Text("\(entryCount) entries")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            if let category = entity.category, !category.isEmpty {
                                Text(category)
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                            if let netAmountMinor = entity.netAmountMinor, let currencyCode = entity.netAmountCurrencyCode {
                                Text(FinanceFormatters.signedCurrency(netAmountMinor, currencyCode: currencyCode))
                                    .font(.caption.monospacedDigit())
                                    .foregroundStyle(.secondary)
                            } else if entity.netAmountMixedCurrencies {
                                Text("Net total spans multiple currencies")
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        .padding(.vertical, 4)
                        .swipeActions(edge: .trailing) {
                            if canEdit && !entity.isAccount {
                                Button(role: .destructive) {
                                    deletionTarget = entity
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }
                        .swipeActions(edge: .leading) {
                            if canEdit && !entity.isAccount {
                                Button {
                                    editorMode = .edit(entity)
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(.indigo)
                            }
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Entities")
        .searchable(text: $searchText, prompt: "Search entities")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .toolbar {
            if canEdit {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editorMode = .create
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
        }
        .sheet(item: $editorMode) { mode in
            EntityEditorSheet(mode: mode) { draft in
                try await model.save(mode: mode, draft: draft)
            }
        }
        .alert("Delete entity?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
            Button("Delete", role: .destructive) {
                guard let deletionTarget else { return }
                Task {
                    do {
                        try await model.delete(entity: deletionTarget)
                    } catch {
                        model.errorMessage = error.localizedDescription
                    }
                    self.deletionTarget = nil
                }
            }
            Button("Cancel", role: .cancel) {
                deletionTarget = nil
            }
        } message: {
            Text("Account-backed entities must be managed through Accounts.")
        }
    }
}

private enum EntityEditorMode: Identifiable {
    case create
    case edit(Entity)

    var id: String {
        switch self {
        case .create:
            return "create-entity"
        case .edit(let entity):
            return "edit-entity-\(entity.id)"
        }
    }
}

private struct EntityDraft {
    var name: String
    var category: String?

    init(entity: Entity? = nil) {
        name = entity?.name ?? ""
        category = entity?.category
    }
}

private struct EntityEditorSheet: View {
    let mode: EntityEditorMode
    let onSave: (EntityDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var draft: EntityDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(mode: EntityEditorMode, onSave: @escaping (EntityDraft) async throws -> Void) {
        self.mode = mode
        self.onSave = onSave
        switch mode {
        case .create:
            _draft = State(initialValue: EntityDraft())
        case .edit(let entity):
            _draft = State(initialValue: EntityDraft(entity: entity))
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Name", text: $draft.name)
                    TextField("Category", text: Binding(
                        get: { draft.category ?? "" },
                        set: { draft.category = normalizedOptional($0) }
                    ))
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New Entity"
        case .edit:
            return "Edit Entity"
        }
    }

    private func save() async {
        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !draft.name.isEmpty else {
            errorMessage = "Entity name is required."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(draft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
private final class TagsWorkspaceModel: ObservableObject {
    @Published private(set) var tags: [Tag] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }
        do {
            tags = try await apiClient.listTags().sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(mode: TagEditorMode, draft: TagDraft) async throws {
        switch mode {
        case .create:
            _ = try await apiClient.createTag(
                TagCreatePayload(
                    name: draft.name,
                    color: draft.color,
                    description: draft.description,
                    type: draft.type
                )
            )
        case .edit(let tag):
            _ = try await apiClient.updateTag(
                id: tag.id,
                payload: TagUpdatePayload(
                    name: draft.name,
                    color: draft.color,
                    description: draft.description,
                    type: draft.type
                )
            )
        }
        await reload()
    }

    func delete(tag: Tag) async throws {
        try await apiClient.deleteTag(id: tag.id)
        await reload()
    }
}

private struct TagsWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    @StateObject private var model: TagsWorkspaceModel
    @State private var searchText = ""
    @State private var editorMode: TagEditorMode?
    @State private var deletionTarget: Tag?

    init(apiClient: APIClient, canEdit: Bool) {
        self.apiClient = apiClient
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: TagsWorkspaceModel(apiClient: apiClient))
    }

    private var filteredTags: [Tag] {
        model.tags.filter { tag in
            searchText.isEmpty
                || tag.name.localizedCaseInsensitiveContains(searchText)
                || (tag.type ?? "").localizedCaseInsensitiveContains(searchText)
                || (tag.description ?? "").localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        List {
            if !canEdit {
                Section {
                    ManageReadOnlyNote(text: "Tag writes require an admin principal. Counts still reflect your visible entries.")
                }
            }

            if let errorMessage = model.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            Section("Tags") {
                if filteredTags.isEmpty {
                    ManageEmptyRow(text: searchText.isEmpty ? "No tags available" : "No tags match the current search")
                } else {
                    ForEach(filteredTags) { tag in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(tag.name)
                                    .font(.body.weight(.semibold))
                                if let color = tag.color, !color.isEmpty {
                                    ManageBadge(text: color, tint: .indigo)
                                }
                                Spacer()
                                if let entryCount = tag.entryCount {
                                    Text("\(entryCount) entries")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            if let type = tag.type, !type.isEmpty {
                                Text(type)
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                            if let description = tag.description, !description.isEmpty {
                                Text(description)
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                                    .lineLimit(2)
                            }
                        }
                        .padding(.vertical, 4)
                        .swipeActions(edge: .trailing) {
                            if canEdit {
                                Button(role: .destructive) {
                                    deletionTarget = tag
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }
                        .swipeActions(edge: .leading) {
                            if canEdit {
                                Button {
                                    editorMode = .edit(tag)
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(.indigo)
                            }
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Tags")
        .searchable(text: $searchText, prompt: "Search tags")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .toolbar {
            if canEdit {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editorMode = .create
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
        }
        .sheet(item: $editorMode) { mode in
            TagEditorSheet(mode: mode) { draft in
                try await model.save(mode: mode, draft: draft)
            }
        }
        .alert("Delete tag?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
            Button("Delete", role: .destructive) {
                guard let deletionTarget else { return }
                Task {
                    do {
                        try await model.delete(tag: deletionTarget)
                    } catch {
                        model.errorMessage = error.localizedDescription
                    }
                    self.deletionTarget = nil
                }
            }
            Button("Cancel", role: .cancel) {
                deletionTarget = nil
            }
        } message: {
            Text("Deleting a tag removes future catalog access but existing entry references are cleaned up by the backend.")
        }
    }
}

private enum TagEditorMode: Identifiable {
    case create
    case edit(Tag)

    var id: String {
        switch self {
        case .create:
            return "create-tag"
        case .edit(let tag):
            return "edit-tag-\(tag.id)"
        }
    }
}

private struct TagDraft {
    var name: String
    var color: String?
    var description: String?
    var type: String?

    init(tag: Tag? = nil) {
        name = tag?.name ?? ""
        color = tag?.color
        description = tag?.description
        type = tag?.type
    }
}

private struct TagEditorSheet: View {
    let mode: TagEditorMode
    let onSave: (TagDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var draft: TagDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(mode: TagEditorMode, onSave: @escaping (TagDraft) async throws -> Void) {
        self.mode = mode
        self.onSave = onSave
        switch mode {
        case .create:
            _draft = State(initialValue: TagDraft())
        case .edit(let tag):
            _draft = State(initialValue: TagDraft(tag: tag))
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Name", text: $draft.name)
                    TextField("Color", text: Binding(
                        get: { draft.color ?? "" },
                        set: { draft.color = normalizedOptional($0) }
                    ))
                    TextField("Type", text: Binding(
                        get: { draft.type ?? "" },
                        set: { draft.type = normalizedOptional($0) }
                    ))
                    TextField("Description", text: Binding(
                        get: { draft.description ?? "" },
                        set: { draft.description = normalizedOptional($0) }
                    ), axis: .vertical)
                    .lineLimit(2 ... 6)
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New Tag"
        case .edit:
            return "Edit Tag"
        }
    }

    private func save() async {
        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !draft.name.isEmpty else {
            errorMessage = "Tag name is required."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(draft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
private final class GroupsWorkspaceModel: ObservableObject {
    @Published private(set) var groups: [GroupSummary] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }
        do {
            groups = try await apiClient.listGroups().sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(mode: GroupEditorMode, draft: GroupDraft) async throws {
        switch mode {
        case .create:
            _ = try await apiClient.createGroup(GroupCreatePayload(name: draft.name, groupType: draft.groupType))
        case .edit(let group):
            _ = try await apiClient.updateGroup(id: group.id, payload: GroupUpdatePayload(name: draft.name))
        }
        await reload()
    }

    func delete(group: GroupSummary) async throws {
        try await apiClient.deleteGroup(id: group.id)
        await reload()
    }
}

private struct GroupsWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    @StateObject private var model: GroupsWorkspaceModel
    @State private var searchText = ""
    @State private var editorMode: GroupEditorMode?
    @State private var deletionTarget: GroupSummary?
    @State private var selectedGroup: GroupSummary?

    init(apiClient: APIClient, canEdit: Bool) {
        self.apiClient = apiClient
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: GroupsWorkspaceModel(apiClient: apiClient))
    }

    private var filteredGroups: [GroupSummary] {
        model.groups.filter { group in
            searchText.isEmpty || group.name.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        List {
            if let errorMessage = model.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            Section("Groups") {
                if filteredGroups.isEmpty {
                    ManageEmptyRow(text: searchText.isEmpty ? "No groups yet" : "No groups match the current search")
                } else {
                    ForEach(filteredGroups) { group in
                        Button {
                            selectedGroup = group
                        } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(group.name)
                                        .font(.body.weight(.semibold))
                                        .foregroundStyle(.primary)
                                    ManageBadge(text: group.groupType.rawValue.capitalized, tint: tint(for: group.groupType))
                                    Spacer()
                                    Text("\(group.descendantEntryCount) entries")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                HStack(spacing: 10) {
                                    Text("\(group.directEntryCount) direct entries")
                                    Text("\(group.directChildGroupCount) child groups")
                                    if group.parentGroupId != nil {
                                        Text("Nested")
                                    }
                                }
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                if let firstOccurredAt = group.firstOccurredAt, let lastOccurredAt = group.lastOccurredAt {
                                    Text("\(firstOccurredAt) → \(lastOccurredAt)")
                                        .font(.caption)
                                        .foregroundStyle(.tertiary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                        .buttonStyle(.plain)
                        .swipeActions(edge: .trailing) {
                            if canEdit {
                                Button(role: .destructive) {
                                    deletionTarget = group
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }
                        .swipeActions(edge: .leading) {
                            if canEdit {
                                Button {
                                    editorMode = .edit(group)
                                } label: {
                                    Label("Rename", systemImage: "pencil")
                                }
                                .tint(.indigo)
                            }
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Groups")
        .searchable(text: $searchText, prompt: "Search groups")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .toolbar {
            if canEdit {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editorMode = .create
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
        }
        .sheet(item: $editorMode) { mode in
            GroupEditorSheet(mode: mode) { draft in
                try await model.save(mode: mode, draft: draft)
            }
        }
        .navigationDestination(item: $selectedGroup) { group in
            GroupDetailView(apiClient: apiClient, groupID: group.id, canEdit: canEdit)
        }
        .alert("Delete group?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
            Button("Delete", role: .destructive) {
                guard let deletionTarget else { return }
                Task {
                    do {
                        try await model.delete(group: deletionTarget)
                    } catch {
                        model.errorMessage = error.localizedDescription
                    }
                    self.deletionTarget = nil
                }
            }
            Button("Cancel", role: .cancel) {
                deletionTarget = nil
            }
        } message: {
            Text("A group can only be deleted when it has no direct members and is not nested.")
        }
    }

    private func tint(for type: GroupType) -> Color {
        switch type {
        case .bundle:
            return .indigo
        case .split:
            return .orange
        case .recurring:
            return .green
        }
    }
}

private enum GroupEditorMode: Identifiable {
    case create
    case edit(GroupSummary)

    var id: String {
        switch self {
        case .create:
            return "create-group"
        case .edit(let group):
            return "edit-group-\(group.id)"
        }
    }
}

private struct GroupDraft {
    var name: String
    var groupType: GroupType

    init(group: GroupSummary? = nil) {
        name = group?.name ?? ""
        groupType = group?.groupType ?? .bundle
    }
}

private struct GroupEditorSheet: View {
    let mode: GroupEditorMode
    let onSave: (GroupDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var draft: GroupDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(mode: GroupEditorMode, onSave: @escaping (GroupDraft) async throws -> Void) {
        self.mode = mode
        self.onSave = onSave
        switch mode {
        case .create:
            _draft = State(initialValue: GroupDraft())
        case .edit(let group):
            _draft = State(initialValue: GroupDraft(group: group))
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Name", text: $draft.name)
                    if case .create = mode {
                        Picker("Type", selection: $draft.groupType) {
                            ForEach(GroupType.allCases, id: \.self) { type in
                                Text(type.rawValue.capitalized).tag(type)
                            }
                        }
                    } else {
                        LabeledContent("Type", value: draft.groupType.rawValue.capitalized)
                    }
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New Group"
        case .edit:
            return "Rename Group"
        }
    }

    private func save() async {
        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !draft.name.isEmpty else {
            errorMessage = "Group name is required."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(draft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
private final class GroupDetailModel: ObservableObject {
    @Published private(set) var group: GroupGraph?
    @Published private(set) var allEntries: [Entry] = []
    @Published private(set) var allGroups: [GroupSummary] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    private let apiClient: APIClient
    private let groupID: String

    init(apiClient: APIClient, groupID: String) {
        self.apiClient = apiClient
        self.groupID = groupID
    }

    func reload() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let groupTask = apiClient.group(id: groupID)
            async let entriesTask = apiClient.listEntries(query: EntryListQuery(limit: 200))
            async let groupsTask = apiClient.listGroups()
            group = try await groupTask
            allEntries = try await entriesTask.items
            allGroups = try await groupsTask
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func addMember(target: GroupMemberTarget, role: GroupMemberRole?) async throws {
        _ = try await apiClient.addGroupMember(groupID: groupID, payload: GroupMemberCreatePayload(target: target, memberRole: role))
        await reload()
    }

    func deleteMembership(membershipID: String) async throws {
        try await apiClient.deleteGroupMember(groupID: groupID, membershipID: membershipID)
        await reload()
    }
}

private struct GroupDetailView: View {
    let apiClient: APIClient
    let groupID: String
    let canEdit: Bool

    @StateObject private var model: GroupDetailModel
    @State private var addMemberPresented = false
    @State private var memberToDelete: GroupNode?

    init(apiClient: APIClient, groupID: String, canEdit: Bool) {
        self.apiClient = apiClient
        self.groupID = groupID
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: GroupDetailModel(apiClient: apiClient, groupID: groupID))
    }

    private var directMembers: [GroupNode] {
        guard let group = model.group else { return [] }
        guard let root = group.nodes.first(where: { $0.subjectId == group.id }) else { return group.nodes }
        let targetGraphIDs = Set(group.edges.filter { $0.sourceGraphId == root.graphId }.map(\.targetGraphId))
        return group.nodes.filter { targetGraphIDs.contains($0.graphId) }
    }

    var body: some View {
        Group {
            if model.isLoading && model.group == nil {
                ManageLoadingState(title: "Loading group…")
            } else if let group = model.group {
                List {
                    Section("Overview") {
                        LabeledContent("Type", value: group.groupType.rawValue.capitalized)
                        LabeledContent("Direct members", value: "\(group.directMemberCount)")
                        LabeledContent("Direct entries", value: "\(group.directEntryCount)")
                        LabeledContent("Child groups", value: "\(group.directChildGroupCount)")
                        LabeledContent("Descendant entries", value: "\(group.descendantEntryCount)")
                        if let firstOccurredAt = group.firstOccurredAt, let lastOccurredAt = group.lastOccurredAt {
                            LabeledContent("Date span", value: "\(firstOccurredAt) → \(lastOccurredAt)")
                        }
                    }

                    if let errorMessage = model.errorMessage {
                        Section {
                            ManageInlineError(message: errorMessage)
                        }
                    }

                    Section("Members") {
                        if directMembers.isEmpty {
                            ManageEmptyRow(text: "No direct members yet")
                        } else {
                            ForEach(directMembers, id: \.graphId) { node in
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        Text(node.name)
                                            .font(.body.weight(.semibold))
                                        if let memberRole = node.memberRole {
                                            ManageBadge(text: memberRole.rawValue.capitalized, tint: .orange)
                                        }
                                        Spacer()
                                        Text(node.nodeType.capitalized)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    if let occurredAt = node.occurredAt ?? node.representativeOccurredAt {
                                        Text(occurredAt)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    if let amountMinor = node.amountMinor, let currencyCode = node.currencyCode {
                                        Text(FinanceFormatters.signedCurrency(amountMinor, currencyCode: currencyCode))
                                            .font(.caption.monospacedDigit())
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                .padding(.vertical, 4)
                                .swipeActions(edge: .trailing) {
                                    if canEdit {
                                        Button(role: .destructive) {
                                            memberToDelete = node
                                        } label: {
                                            Label("Remove", systemImage: "minus.circle")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .listStyle(.insetGrouped)
                .navigationTitle(group.name)
                .toolbar {
                    if canEdit {
                        ToolbarItem(placement: .topBarTrailing) {
                            Button {
                                addMemberPresented = true
                            } label: {
                                Image(systemName: "plus")
                            }
                        }
                    }
                }
                .sheet(isPresented: $addMemberPresented) {
                    GroupMemberEditorSheet(
                        group: group,
                        allEntries: model.allEntries,
                        allGroups: model.allGroups
                    ) { target, role in
                        try await model.addMember(target: target, role: role)
                    }
                }
                .alert("Remove member?", isPresented: Binding(get: { memberToDelete != nil }, set: { if !$0 { memberToDelete = nil } })) {
                    Button("Remove", role: .destructive) {
                        guard let memberToDelete else { return }
                        Task {
                            do {
                                try await model.deleteMembership(membershipID: memberToDelete.membershipId)
                            } catch {
                                model.errorMessage = error.localizedDescription
                            }
                            self.memberToDelete = nil
                        }
                    }
                    Button("Cancel", role: .cancel) {
                        memberToDelete = nil
                    }
                } message: {
                    Text("Removing a direct member updates the group graph immediately.")
                }
            } else if let errorMessage = model.errorMessage {
                ManageErrorState(title: "Couldn’t load group", message: errorMessage) {
                    await model.reload()
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .task { await model.reload() }
    }
}

private struct GroupMemberEditorSheet: View {
    let group: GroupGraph
    let allEntries: [Entry]
    let allGroups: [GroupSummary]
    let onSave: (GroupMemberTarget, GroupMemberRole?) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var mode: MemberTargetMode = .entry
    @State private var selectedEntryID = ""
    @State private var selectedGroupID = ""
    @State private var selectedRole: GroupMemberRole = .child
    @State private var errorMessage: String?
    @State private var isSaving = false

    private var availableChildGroups: [GroupSummary] {
        allGroups.filter { candidate in
            candidate.id != group.id && candidate.parentGroupId == nil
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Target") {
                    Picker("Member type", selection: $mode) {
                        ForEach(MemberTargetMode.allCases, id: \.self) { mode in
                            Text(mode.title).tag(mode)
                        }
                    }

                    switch mode {
                    case .entry:
                        Picker("Entry", selection: $selectedEntryID) {
                            Text("Choose an entry").tag("")
                            ForEach(allEntries) { entry in
                                Text("\(entry.name) · \(entry.occurredAt)").tag(entry.id)
                            }
                        }
                    case .childGroup:
                        Picker("Child group", selection: $selectedGroupID) {
                            Text("Choose a group").tag("")
                            ForEach(availableChildGroups) { group in
                                Text(group.name).tag(group.id)
                            }
                        }
                    }
                }

                if group.groupType == .split {
                    Section("Split role") {
                        Picker("Role", selection: $selectedRole) {
                            ForEach(GroupMemberRole.allCases, id: \.self) { role in
                                Text(role.rawValue.capitalized).tag(role)
                            }
                        }
                    }
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle("Add Member")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Adding…" : "Add") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func save() async {
        let target: GroupMemberTarget
        switch mode {
        case .entry:
            guard !selectedEntryID.isEmpty else {
                errorMessage = "Choose an entry to add."
                return
            }
            target = .entry(entryId: selectedEntryID)
        case .childGroup:
            guard !selectedGroupID.isEmpty else {
                errorMessage = "Choose a child group to add."
                return
            }
            target = .childGroup(groupId: selectedGroupID)
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(target, group.groupType == .split ? selectedRole : nil)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private enum MemberTargetMode: CaseIterable {
    case entry
    case childGroup

    var title: String {
        switch self {
        case .entry:
            return "Entry"
        case .childGroup:
            return "Child Group"
        }
    }
}

@MainActor
private final class FilterGroupsWorkspaceModel: ObservableObject {
    @Published private(set) var groups: [FilterGroup] = []
    @Published private(set) var tags: [Tag] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }
        do {
            async let groupsTask = apiClient.listFilterGroups()
            async let tagsTask = apiClient.listTags()
            groups = try await groupsTask.sorted(by: { $0.position < $1.position })
            tags = try await tagsTask.sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(mode: FilterGroupEditorMode, draft: FilterGroupDraft) async throws {
        switch mode {
        case .create:
            _ = try await apiClient.createFilterGroup(
                FilterGroupCreatePayload(
                    name: draft.name,
                    description: draft.description,
                    color: draft.color,
                    rule: draft.rule
                )
            )
        case .edit(let group):
            _ = try await apiClient.updateFilterGroup(
                id: group.id,
                payload: FilterGroupUpdatePayload(
                    name: group.isDefault ? nil : draft.name,
                    description: draft.description,
                    color: draft.color,
                    rule: draft.rule
                )
            )
        }
        await reload()
    }

    func delete(group: FilterGroup) async throws {
        try await apiClient.deleteFilterGroup(id: group.id)
        await reload()
    }
}

private struct FilterGroupsWorkspaceView: View {
    let apiClient: APIClient

    @StateObject private var model: FilterGroupsWorkspaceModel
    @State private var searchText = ""
    @State private var editorMode: FilterGroupEditorMode?
    @State private var deletionTarget: FilterGroup?

    init(apiClient: APIClient) {
        self.apiClient = apiClient
        _model = StateObject(wrappedValue: FilterGroupsWorkspaceModel(apiClient: apiClient))
    }

    private var filteredGroups: [FilterGroup] {
        model.groups.filter { group in
            searchText.isEmpty
                || group.name.localizedCaseInsensitiveContains(searchText)
                || group.ruleSummary.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        List {
            if let errorMessage = model.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            Section("Filter groups") {
                if filteredGroups.isEmpty {
                    ManageEmptyRow(text: searchText.isEmpty ? "No filter groups available" : "No filter groups match the current search")
                } else {
                    ForEach(filteredGroups) { group in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text(group.name)
                                    .font(.body.weight(.semibold))
                                if group.isDefault {
                                    ManageBadge(text: "Default", tint: .secondary)
                                }
                                if let color = group.color, !color.isEmpty {
                                    ManageBadge(text: color, tint: .indigo)
                                }
                                Spacer()
                            }
                            if let description = group.description, !description.isEmpty {
                                Text(description)
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                            }
                            Text(group.ruleSummary)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                        .swipeActions(edge: .trailing) {
                            if !group.isDefault {
                                Button(role: .destructive) {
                                    deletionTarget = group
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }
                        .swipeActions(edge: .leading) {
                            Button {
                                editorMode = .edit(group)
                            } label: {
                                Label("Edit", systemImage: "pencil")
                            }
                            .tint(.indigo)
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Filter Groups")
        .searchable(text: $searchText, prompt: "Search filter groups")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    editorMode = .create
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(item: $editorMode) { mode in
            FilterGroupEditorSheet(mode: mode, tags: model.tags) { draft in
                try await model.save(mode: mode, draft: draft)
            }
        }
        .alert("Delete filter group?", isPresented: Binding(get: { deletionTarget != nil }, set: { if !$0 { deletionTarget = nil } })) {
            Button("Delete", role: .destructive) {
                guard let deletionTarget else { return }
                Task {
                    do {
                        try await model.delete(group: deletionTarget)
                    } catch {
                        model.errorMessage = error.localizedDescription
                    }
                    self.deletionTarget = nil
                }
            }
            Button("Cancel", role: .cancel) {
                deletionTarget = nil
            }
        } message: {
            Text("Built-in default filter groups cannot be deleted.")
        }
    }
}

private enum FilterGroupEditorMode: Identifiable {
    case create
    case edit(FilterGroup)

    var id: String {
        switch self {
        case .create:
            return "create-filter-group"
        case .edit(let group):
            return "edit-filter-group-\(group.id)"
        }
    }
}

private struct FilterGroupDraft {
    var name: String
    var description: String?
    var color: String?
    var rule: FilterGroupRule

    init(group: FilterGroup? = nil) {
        name = group?.name ?? "New Group"
        description = group?.description
        color = group?.color
        rule = group?.rule ?? FilterGroupRule(
            include: FilterRuleGroup(
                operator: .and,
                children: [.condition(FilterRuleCondition(field: .entryKind, operator: .is, value: .string(EntryKind.expense.rawValue)))]
            ),
            exclude: nil
        )
    }
}

private struct FilterGroupEditorSheet: View {
    let mode: FilterGroupEditorMode
    let tags: [Tag]
    let onSave: (FilterGroupDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var draft: FilterGroupDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(mode: FilterGroupEditorMode, tags: [Tag], onSave: @escaping (FilterGroupDraft) async throws -> Void) {
        self.mode = mode
        self.tags = tags
        self.onSave = onSave
        switch mode {
        case .create:
            _draft = State(initialValue: FilterGroupDraft())
        case .edit(let group):
            _draft = State(initialValue: FilterGroupDraft(group: group))
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    if !isDefault {
                        TextField("Name", text: $draft.name)
                    } else {
                        LabeledContent("Name", value: draft.name)
                    }
                    TextField("Description", text: Binding(
                        get: { draft.description ?? "" },
                        set: { draft.description = normalizedOptional($0) }
                    ), axis: .vertical)
                    .lineLimit(2 ... 6)
                    TextField("Color", text: Binding(
                        get: { draft.color ?? "" },
                        set: { draft.color = normalizedOptional($0) }
                    ))
                }

                FilterRuleGroupEditor(group: $draft.rule.include, title: "Include rules", tags: tags)

                Section("Exclude rules") {
                    Toggle("Enable exclude rules", isOn: Binding(
                        get: { draft.rule.exclude != nil },
                        set: { isEnabled in
                            draft.rule.exclude = isEnabled ? FilterRuleGroup(operator: .and, children: []) : nil
                        }
                    ))

                    if draft.rule.exclude != nil {
                        FilterRuleGroupEditor(group: Binding(
                            get: { draft.rule.exclude ?? FilterRuleGroup(operator: .and, children: []) },
                            set: { draft.rule.exclude = $0 }
                        ), title: "Exclude rules", tags: tags)
                    }
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private var isDefault: Bool {
        if case .edit(let group) = mode {
            return group.isDefault
        }
        return false
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New Filter Group"
        case .edit:
            return "Edit Filter Group"
        }
    }

    private func save() async {
        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        if !isDefault && draft.name.isEmpty {
            errorMessage = "Filter group name is required."
            return
        }
        if draft.rule.include.children.isEmpty {
            errorMessage = "Add at least one include rule."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(draft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct FilterRuleGroupEditor: View {
    @Binding var group: FilterRuleGroup
    let title: String
    let tags: [Tag]

    var body: some View {
        Section(title) {
            Picker("Operator", selection: $group.operator) {
                ForEach(FilterRuleLogicalOperator.allCases, id: \.self) { op in
                    Text(op.rawValue).tag(op)
                }
            }

            if group.children.isEmpty {
                ManageEmptyRow(text: "No rules yet")
            } else {
                ForEach(group.children.indices, id: \.self) { index in
                    FilterRuleNodeEditor(
                        node: Binding(
                            get: { group.children[index] },
                            set: { group.children[index] = $0 }
                        ),
                        tags: tags
                    ) {
                        group.children.remove(at: index)
                    }
                }
            }

            Button {
                group.children.append(.condition(FilterRuleCondition(field: .entryKind, operator: .is, value: .string(EntryKind.expense.rawValue))))
            } label: {
                Label("Add condition", systemImage: "plus.circle")
            }

            Button {
                group.children.append(.group(FilterRuleGroup(operator: .and, children: [])))
            } label: {
                Label("Add subgroup", systemImage: "plus.square.on.square")
            }
        }
    }
}

private struct FilterRuleNodeEditor: View {
    @Binding var node: FilterRuleNode
    let tags: [Tag]
    let onDelete: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Picker("Rule type", selection: nodeTypeBinding) {
                    ForEach(FilterRuleNodeKind.allCases, id: \.self) { kind in
                        Text(kind.title).tag(kind)
                    }
                }
                Button(role: .destructive, action: onDelete) {
                    Image(systemName: "trash")
                }
            }

            switch node {
            case .condition:
                FilterRuleConditionEditor(condition: conditionBinding, tags: tags)
            case .group:
                FilterRuleGroupEditor(group: groupBinding, title: "Nested rules", tags: tags)
            }
        }
        .padding(.vertical, 8)
    }

    private var nodeTypeBinding: Binding<FilterRuleNodeKind> {
        Binding(
            get: {
                switch node {
                case .condition:
                    return .condition
                case .group:
                    return .group
                }
            },
            set: { newValue in
                switch newValue {
                case .condition:
                    node = .condition(FilterRuleCondition(field: .entryKind, operator: .is, value: .string(EntryKind.expense.rawValue)))
                case .group:
                    node = .group(FilterRuleGroup(operator: .and, children: []))
                }
            }
        )
    }

    private var conditionBinding: Binding<FilterRuleCondition> {
        Binding(
            get: {
                if case .condition(let condition) = node {
                    return condition
                }
                return FilterRuleCondition(field: .entryKind, operator: .is, value: .string(EntryKind.expense.rawValue))
            },
            set: { node = .condition($0) }
        )
    }

    private var groupBinding: Binding<FilterRuleGroup> {
        Binding(
            get: {
                if case .group(let group) = node {
                    return group
                }
                return FilterRuleGroup(operator: .and, children: [])
            },
            set: { node = .group($0) }
        )
    }
}

private enum FilterRuleNodeKind: CaseIterable {
    case condition
    case group

    var title: String {
        switch self {
        case .condition:
            return "Condition"
        case .group:
            return "Group"
        }
    }
}

private struct FilterRuleConditionEditor: View {
    @Binding var condition: FilterRuleCondition
    let tags: [Tag]

    private var tagNames: String {
        if case .strings(let values) = condition.value {
            return values.joined(separator: ", ")
        }
        return ""
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Field", selection: $condition.field) {
                ForEach(FilterRuleField.allCases, id: \.self) { field in
                    Text(fieldTitle(field)).tag(field)
                }
            }
            .onChange(of: condition.field) { _, newField in
                switch newField {
                case .entryKind:
                    condition.operator = .is
                    condition.value = .string(EntryKind.expense.rawValue)
                case .tags:
                    condition.operator = .hasAny
                    condition.value = .strings([])
                case .isInternalTransfer:
                    condition.operator = .is
                    condition.value = .boolean(false)
                }
            }

            Picker("Operator", selection: $condition.operator) {
                ForEach(operatorOptions(for: condition.field), id: \.self) { op in
                    Text(opTitle(op)).tag(op)
                }
            }

            switch condition.field {
            case .entryKind:
                Picker("Value", selection: entryKindValueBinding) {
                    ForEach(EntryKind.allCases, id: \.self) { kind in
                        Text(entryKindTitle(kind)).tag(kind.rawValue)
                    }
                }
            case .tags:
                TextField("Tags (comma-separated)", text: tagListBinding)
                if !tags.isEmpty {
                    Text(tags.map(\.name).joined(separator: ", "))
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            case .isInternalTransfer:
                Toggle("Internal transfer", isOn: booleanBinding)
            }
        }
    }

    private var entryKindValueBinding: Binding<String> {
        Binding(
            get: {
                if case .string(let value) = condition.value {
                    return value
                }
                return EntryKind.expense.rawValue
            },
            set: { condition.value = .string($0) }
        )
    }

    private var booleanBinding: Binding<Bool> {
        Binding(
            get: {
                if case .boolean(let value) = condition.value {
                    return value
                }
                return false
            },
            set: { condition.value = .boolean($0) }
        )
    }

    private var tagListBinding: Binding<String> {
        Binding(
            get: { tagNames },
            set: {
                condition.value = .strings(
                    $0.split(separator: ",")
                        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                        .filter { !$0.isEmpty }
                )
            }
        )
    }

    private func operatorOptions(for field: FilterRuleField) -> [FilterRuleConditionOperator] {
        switch field {
        case .entryKind, .isInternalTransfer:
            return [.is]
        case .tags:
            return [.hasAny, .hasNone]
        }
    }

    private func fieldTitle(_ field: FilterRuleField) -> String {
        switch field {
        case .entryKind:
            return "Entry kind"
        case .tags:
            return "Tags"
        case .isInternalTransfer:
            return "Internal transfer"
        }
    }

    private func opTitle(_ op: FilterRuleConditionOperator) -> String {
        switch op {
        case .is:
            return "is"
        case .hasAny:
            return "has any"
        case .hasNone:
            return "has none"
        }
    }
}

@MainActor
private final class TaxonomiesWorkspaceModel: ObservableObject {
    @Published private(set) var taxonomies: [Taxonomy] = []
    @Published private(set) var termsByTaxonomy: [String: [TaxonomyTerm]] = [:]
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }
        do {
            let taxonomies = try await apiClient.listTaxonomies().sorted(by: { $0.displayName.localizedCaseInsensitiveCompare($1.displayName) == .orderedAscending })
            self.taxonomies = taxonomies
            var termsByTaxonomy: [String: [TaxonomyTerm]] = [:]
            for taxonomy in taxonomies {
                termsByTaxonomy[taxonomy.key] = try await apiClient.listTaxonomyTerms(taxonomyKey: taxonomy.key)
                    .sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            }
            self.termsByTaxonomy = termsByTaxonomy
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(draft: TaxonomyTermDraft) async throws {
        if let termID = draft.termID {
            _ = try await apiClient.updateTaxonomyTerm(
                taxonomyKey: draft.taxonomyKey,
                termID: termID,
                payload: TaxonomyTermUpdatePayload(name: draft.name, description: draft.description)
            )
        } else {
            _ = try await apiClient.createTaxonomyTerm(
                taxonomyKey: draft.taxonomyKey,
                payload: TaxonomyTermCreatePayload(name: draft.name, description: draft.description)
            )
        }
        await reload()
    }
}

private struct TaxonomiesWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    @StateObject private var model: TaxonomiesWorkspaceModel
    @State private var searchText = ""
    @State private var editorDraft: TaxonomyTermDraft?

    init(apiClient: APIClient, canEdit: Bool) {
        self.apiClient = apiClient
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: TaxonomiesWorkspaceModel(apiClient: apiClient))
    }

    var body: some View {
        List {
            if !canEdit {
                Section {
                    ManageReadOnlyNote(text: "Taxonomy term writes require an admin principal.")
                }
            }

            if let errorMessage = model.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            ForEach(model.taxonomies) { taxonomy in
                Section(taxonomy.displayName) {
                    let filteredTerms = (model.termsByTaxonomy[taxonomy.key] ?? []).filter { term in
                        searchText.isEmpty
                            || term.name.localizedCaseInsensitiveContains(searchText)
                            || (term.description ?? "").localizedCaseInsensitiveContains(searchText)
                    }
                    if filteredTerms.isEmpty {
                        ManageEmptyRow(text: searchText.isEmpty ? "No terms yet" : "No terms match the current search")
                    } else {
                        ForEach(filteredTerms) { term in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack {
                                    Text(term.name)
                                        .font(.body.weight(.semibold))
                                    Spacer()
                                    Text("\(term.usageCount) uses")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                if let description = term.description, !description.isEmpty {
                                    Text(description)
                                        .font(.footnote)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                            .swipeActions(edge: .leading) {
                                if canEdit {
                                    Button {
                                        editorDraft = TaxonomyTermDraft(taxonomy: taxonomy, term: term)
                                    } label: {
                                        Label("Edit", systemImage: "pencil")
                                    }
                                    .tint(.indigo)
                                }
                            }
                        }
                    }

                    if canEdit {
                        Button {
                            editorDraft = TaxonomyTermDraft(taxonomy: taxonomy, term: nil)
                        } label: {
                            Label("Add term", systemImage: "plus.circle")
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Taxonomies")
        .searchable(text: $searchText, prompt: "Search taxonomy terms")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .sheet(item: $editorDraft) { draft in
            TaxonomyTermEditorSheet(draft: draft) { updatedDraft in
                try await model.save(draft: updatedDraft)
            }
        }
    }
}

private struct TaxonomyTermDraft: Identifiable {
    let taxonomyKey: String
    let taxonomyDisplayName: String
    let termID: String?
    var name: String
    var description: String?

    var id: String {
        termID ?? "new-\(taxonomyKey)"
    }

    init(taxonomy: Taxonomy, term: TaxonomyTerm?) {
        taxonomyKey = taxonomy.key
        taxonomyDisplayName = taxonomy.displayName
        termID = term?.id
        name = term?.name ?? ""
        description = term?.description
    }
}

private struct TaxonomyTermEditorSheet: View {
    let draft: TaxonomyTermDraft
    let onSave: (TaxonomyTermDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var workingDraft: TaxonomyTermDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(draft: TaxonomyTermDraft, onSave: @escaping (TaxonomyTermDraft) async throws -> Void) {
        self.draft = draft
        self.onSave = onSave
        _workingDraft = State(initialValue: draft)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Taxonomy") {
                    LabeledContent("Definition", value: workingDraft.taxonomyDisplayName)
                }

                Section("Term") {
                    TextField("Name", text: $workingDraft.name)
                    TextField("Description", text: Binding(
                        get: { workingDraft.description ?? "" },
                        set: { workingDraft.description = normalizedOptional($0) }
                    ), axis: .vertical)
                    .lineLimit(2 ... 6)
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(workingDraft.termID == nil ? "New Term" : "Edit Term")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func save() async {
        workingDraft.name = workingDraft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !workingDraft.name.isEmpty else {
            errorMessage = "Term name is required."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(workingDraft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct CurrenciesWorkspaceView: View {
    let apiClient: APIClient

    @State private var currencies: [Currency] = []
    @State private var errorMessage: String?
    @State private var isLoading = true
    @State private var searchText = ""

    private var filteredCurrencies: [Currency] {
        currencies.filter { currency in
            searchText.isEmpty
                || currency.code.localizedCaseInsensitiveContains(searchText)
                || currency.name.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        Group {
            if isLoading && currencies.isEmpty {
                ManageLoadingState(title: "Loading currencies…")
            } else {
                List {
                    if let errorMessage {
                        Section {
                            ManageInlineError(message: errorMessage)
                        }
                    }

                    Section("Currencies") {
                        if filteredCurrencies.isEmpty {
                            ManageEmptyRow(text: searchText.isEmpty ? "No currencies available" : "No currencies match the current search")
                        } else {
                            ForEach(filteredCurrencies, id: \.code) { currency in
                                HStack {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(currency.code)
                                            .font(.body.weight(.semibold))
                                        Text(currency.name)
                                            .font(.footnote)
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    VStack(alignment: .trailing, spacing: 4) {
                                        Text("\(currency.entryCount) entries")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                        if currency.isPlaceholder {
                                            ManageBadge(text: "Placeholder", tint: .orange)
                                        }
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Currencies")
        .searchable(text: $searchText, prompt: "Search currencies")
        .refreshable { await load() }
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            currencies = try await apiClient.listCurrencies().sorted(by: { $0.code.localizedCaseInsensitiveCompare($1.code) == .orderedAscending })
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

@MainActor
private final class UsersWorkspaceModel: ObservableObject {
    @Published private(set) var users: [User] = []
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

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
        isLoading = true
        defer { isLoading = false }
        do {
            users = try await apiClient.listUsers().sorted(by: { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending })
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save(mode: UserEditorMode, draft: UserDraft) async throws {
        switch mode {
        case .create:
            _ = try await apiClient.createUser(UserCreatePayload(name: draft.name))
        case .edit(let user):
            _ = try await apiClient.updateUser(id: user.id, payload: UserUpdatePayload(name: draft.name, isAdmin: draft.isAdmin))
        }
        await reload()
    }
}

private struct UsersWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    @StateObject private var model: UsersWorkspaceModel
    @State private var searchText = ""
    @State private var editorMode: UserEditorMode?

    init(apiClient: APIClient, canEdit: Bool) {
        self.apiClient = apiClient
        self.canEdit = canEdit
        _model = StateObject(wrappedValue: UsersWorkspaceModel(apiClient: apiClient))
    }

    private var filteredUsers: [User] {
        model.users.filter { user in
            searchText.isEmpty || user.name.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        List {
            if !canEdit {
                Section {
                    ManageReadOnlyNote(text: "Only your own user is editable without admin access.")
                }
            }

            if let errorMessage = model.errorMessage {
                Section {
                    ManageInlineError(message: errorMessage)
                }
            }

            Section("Users") {
                if filteredUsers.isEmpty {
                    ManageEmptyRow(text: searchText.isEmpty ? "No users available" : "No users match the current search")
                } else {
                    ForEach(filteredUsers) { user in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(user.name)
                                    .font(.body.weight(.semibold))
                                if user.isCurrentUser {
                                    ManageBadge(text: "Current", tint: .indigo)
                                }
                                if user.isAdmin {
                                    ManageBadge(text: "Admin", tint: .orange)
                                }
                                Spacer()
                            }
                            HStack(spacing: 12) {
                                if let accountCount = user.accountCount {
                                    Text("\(accountCount) accounts")
                                }
                                if let entryCount = user.entryCount {
                                    Text("\(entryCount) entries")
                                }
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                        .swipeActions(edge: .leading) {
                            if canEdit || user.isCurrentUser {
                                Button {
                                    editorMode = .edit(user)
                                } label: {
                                    Label("Edit", systemImage: "pencil")
                                }
                                .tint(.indigo)
                            }
                        }
                    }
                }
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Users")
        .searchable(text: $searchText, prompt: "Search users")
        .refreshable { await model.reload() }
        .task { await model.loadIfNeeded() }
        .toolbar {
            if canEdit {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        editorMode = .create
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
        }
        .sheet(item: $editorMode) { mode in
            UserEditorSheet(mode: mode, canEditAdmin: canEdit) { draft in
                try await model.save(mode: mode, draft: draft)
            }
        }
    }
}

private enum UserEditorMode: Identifiable {
    case create
    case edit(User)

    var id: String {
        switch self {
        case .create:
            return "create-user"
        case .edit(let user):
            return "edit-user-\(user.id)"
        }
    }
}

private struct UserDraft {
    var name: String
    var isAdmin: Bool?

    init(user: User? = nil) {
        name = user?.name ?? ""
        isAdmin = user?.isAdmin
    }
}

private struct UserEditorSheet: View {
    let mode: UserEditorMode
    let canEditAdmin: Bool
    let onSave: (UserDraft) async throws -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var draft: UserDraft
    @State private var errorMessage: String?
    @State private var isSaving = false

    init(mode: UserEditorMode, canEditAdmin: Bool, onSave: @escaping (UserDraft) async throws -> Void) {
        self.mode = mode
        self.canEditAdmin = canEditAdmin
        self.onSave = onSave
        switch mode {
        case .create:
            _draft = State(initialValue: UserDraft())
        case .edit(let user):
            _draft = State(initialValue: UserDraft(user: user))
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Name", text: $draft.name)
                    if case .edit = mode, canEditAdmin {
                        Toggle("Admin", isOn: Binding(
                            get: { draft.isAdmin ?? false },
                            set: { draft.isAdmin = $0 }
                        ))
                    }
                }

                if let errorMessage, !errorMessage.isEmpty {
                    Section {
                        ManageInlineError(message: errorMessage)
                    }
                }
            }
            .navigationTitle(modeTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isSaving ? "Saving…" : "Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private var modeTitle: String {
        switch mode {
        case .create:
            return "New User"
        case .edit:
            return "Edit User"
        }
    }

    private func save() async {
        draft.name = draft.name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !draft.name.isEmpty else {
            errorMessage = "User name is required."
            return
        }

        isSaving = true
        defer { isSaving = false }

        do {
            try await onSave(draft)
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct ManageLoadingState: View {
    let title: String

    var body: some View {
        ProgressView(title)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct ManageErrorState: View {
    let title: String
    let message: String
    let retry: () async -> Void

    var body: some View {
        ContentUnavailableView {
            Label(title, systemImage: "exclamationmark.triangle")
        } description: {
            Text(message)
        } actions: {
            Button("Try again") {
                Task { await retry() }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemGroupedBackground))
    }
}

private struct ManageInlineError: View {
    let message: String

    var body: some View {
        Label(message, systemImage: "exclamationmark.triangle.fill")
            .font(.footnote)
            .foregroundStyle(.red)
    }
}

private struct ManageReadOnlyNote: View {
    let text: String

    var body: some View {
        Label(text, systemImage: "lock")
            .font(.footnote)
            .foregroundStyle(.secondary)
    }
}

private struct ManageEmptyRow: View {
    let text: String

    var body: some View {
        Text(text)
            .foregroundStyle(.secondary)
    }
}

private struct ManageMetric: View {
    let title: String
    let value: String
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline.monospacedDigit())
                .foregroundStyle(tint)
        }
    }
}

private struct ManageBadge: View {
    let text: String
    let tint: Color

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(tint.opacity(0.12), in: Capsule())
            .foregroundStyle(tint)
    }
}

private func normalizedOptional(_ value: String) -> String? {
    let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
    return trimmed.isEmpty ? nil : trimmed
}

private func lineSeparatedValues(from text: String) -> [String]? {
    let values = text
        .split(whereSeparator: \.isNewline)
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
    return values.isEmpty ? [] : values
}

extension Account: Identifiable {}
extension Entry: Identifiable {}
extension Entity: Identifiable {}
extension Tag: Identifiable {}
extension GroupSummary: Identifiable {}
extension FilterGroup: Identifiable {}
extension Taxonomy: Identifiable {}
extension TaxonomyTerm: Identifiable {}
extension User: Identifiable {}

private func entryKindTitle(_ kind: EntryKind) -> String {
    switch kind {
    case .expense:
        return "Expense"
    case .income:
        return "Income"
    case .transfer:
        return "Transfer"
    }
}
