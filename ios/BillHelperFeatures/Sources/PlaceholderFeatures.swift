import SwiftUI

enum ManageRoute: Hashable {
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
    @State private var path: [ManageRoute] = []

    init(apiClient: APIClient, deepLink: Binding<AppDeepLink?>) {
        self.apiClient = apiClient
        _deepLink = deepLink
        _permissionsModel = StateObject(wrappedValue: ManagePermissionsModel(apiClient: apiClient))
    }

    var body: some View {
        List {
            if let errorMessage = permissionsModel.errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(.red)
                }
            }

            Section("Core") {
                NavigationLink(value: ManageRoute.accounts) {
                    manageRow("Accounts", subtitle: "Balances, snapshots, and reconciliation", symbol: "creditcard")
                }
                NavigationLink(value: ManageRoute.groups) {
                    manageRow("Groups", subtitle: "Bundle, split, and recurring groups", symbol: "square.grid.2x2")
                }
                NavigationLink(value: ManageRoute.filterGroups) {
                    manageRow("Filter Groups", subtitle: "Saved filter rules and dashboard scopes", symbol: "line.3.horizontal.decrease.circle")
                }
            }

            Section("Catalogs") {
                NavigationLink(value: ManageRoute.entities) {
                    manageRow("Entities", subtitle: permissionsModel.isAdmin ? "Create and update counterparties" : "Browse visible entities", symbol: "building.2")
                }
                NavigationLink(value: ManageRoute.tags) {
                    manageRow("Tags", subtitle: permissionsModel.isAdmin ? "Manage colors and tag types" : "Browse visible tags", symbol: "tag")
                }
                NavigationLink(value: ManageRoute.taxonomies) {
                    manageRow("Taxonomies", subtitle: "Term catalogs used by entities and tags", symbol: "list.bullet.indent")
                }
                NavigationLink(value: ManageRoute.currencies) {
                    manageRow("Currencies", subtitle: "Read-only currency catalog", symbol: "banknote")
                }
                NavigationLink(value: ManageRoute.users) {
                    manageRow("Users", subtitle: permissionsModel.isAdmin ? "Create and manage app users" : "View your current user profile", symbol: "person.2")
                }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color(.systemGroupedBackground))
        .navigationDestination(for: ManageRoute.self) { route in
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
                path = [.accounts, .account(id)]
                deepLink = nil
            case .group(let id)?:
                path = [.groups, .group(id)]
                deepLink = nil
            default:
                break
            }
        }
    }

    private func manageRow(_ title: String, subtitle: String, symbol: String) -> some View {
        HStack(spacing: 14) {
            Image(systemName: symbol)
                .frame(width: 28, height: 28)
                .foregroundStyle(.indigo)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.body.weight(.semibold))
                Text(subtitle)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

struct SettingsRootView: View {
    @ObservedObject var composition: AppComposition
    @State private var baseURL = ""
    @State private var principalName = ""
    @State private var runtimeSettings: RuntimeSettings?
    @State private var currentUser: User?
    @State private var errorMessage: String?
    @State private var isSavingConnection = false
    @State private var isSavingSettings = false
    @State private var settingsForm = RuntimeSettingsUpdatePayload()

    var body: some View {
        List {
            Section("Session") {
                TextField("Backend URL", text: $baseURL)
                    .textInputAutocapitalization(.never)
                TextField("Principal name", text: $principalName)
                    .textInputAutocapitalization(.never)
                Button(isSavingConnection ? "Reconnecting…" : "Save and reconnect") {
                    Task {
                        isSavingConnection = true
                        await composition.updateConnection(baseURLString: baseURL, principalName: principalName)
                        isSavingConnection = false
                    }
                }
                Button("Sign out", role: .destructive) {
                    composition.signOut()
                }
            }

            if let runtimeSettings {
                Section("Runtime Settings") {
                    TextField("Default currency", text: Binding(
                        get: { settingsForm.defaultCurrencyCode ?? runtimeSettings.defaultCurrencyCode },
                        set: { settingsForm.defaultCurrencyCode = $0 }
                    ))
                    TextField("Dashboard currency", text: Binding(
                        get: { settingsForm.dashboardCurrencyCode ?? runtimeSettings.dashboardCurrencyCode },
                        set: { settingsForm.dashboardCurrencyCode = $0 }
                    ))
                    TextField("Agent model", text: Binding(
                        get: { settingsForm.agentModel ?? runtimeSettings.agentModel },
                        set: { settingsForm.agentModel = $0 }
                    ))
                    TextField("Available models (comma-separated)", text: Binding(
                        get: { (settingsForm.availableAgentModels ?? runtimeSettings.availableAgentModels).joined(separator: ", ") },
                        set: { settingsForm.availableAgentModels = $0.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty } }
                    ))
                    TextField("Max steps", value: Binding(
                        get: { settingsForm.agentMaxSteps ?? runtimeSettings.agentMaxSteps },
                        set: { settingsForm.agentMaxSteps = $0 }
                    ), format: .number)

                    Button(isSavingSettings ? "Saving…" : "Save runtime settings") {
                        Task { await saveRuntimeSettings() }
                    }
                    .disabled(isSavingSettings || !(currentUser?.isAdmin ?? false))
                }
            }

            Section("Diagnostics") {
                LabeledContent("Environment", value: composition.configuration.environment.displayName)
                LabeledContent("Current principal", value: currentUser?.name ?? principalName)
                LabeledContent("Admin", value: (currentUser?.isAdmin ?? false) ? "Yes" : "No")
                if let runtimeSettings {
                    LabeledContent("Image max bytes", value: "\(runtimeSettings.agentMaxImageSizeBytes)")
                    LabeledContent("Images / message", value: "\(runtimeSettings.agentMaxImagesPerMessage)")
                }
            }

            if let errorMessage, !errorMessage.isEmpty {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(.red)
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
            let loadedSettings = try await settingsTask
            runtimeSettings = loadedSettings
            settingsForm = RuntimeSettingsUpdatePayload()
            currentUser = try await usersTask.first(where: \.isCurrentUser)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func saveRuntimeSettings() async {
        guard currentUser?.isAdmin == true else { return }
        isSavingSettings = true
        defer { isSavingSettings = false }
        do {
            runtimeSettings = try await composition.apiClient.updateRuntimeSettings(settingsForm)
            settingsForm = RuntimeSettingsUpdatePayload()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct AccountsWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    var body: some View {
        Text("Accounts workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct EntitiesWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    var body: some View {
        Text("Entities workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct TagsWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    var body: some View {
        Text("Tags workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct GroupsWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    var body: some View {
        Text("Groups workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct GroupDetailView: View {
    let apiClient: APIClient
    let groupID: String
    let canEdit: Bool

    var body: some View {
        Text("Group detail implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct FilterGroupsWorkspaceView: View {
    let apiClient: APIClient

    var body: some View {
        Text("Filter groups workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct TaxonomiesWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    var body: some View {
        Text("Taxonomies workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct CurrenciesWorkspaceView: View {
    let apiClient: APIClient

    var body: some View {
        Text("Currencies workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}

private struct UsersWorkspaceView: View {
    let apiClient: APIClient
    let canEdit: Bool

    var body: some View {
        Text("Users workspace implementation in progress")
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(.systemGroupedBackground))
    }
}
