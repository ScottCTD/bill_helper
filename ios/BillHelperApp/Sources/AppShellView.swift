import SwiftUI

enum AppDestination: String, Hashable, CaseIterable {
    case dashboard
    case entries
    case agent
    case manage
    case settings

    var title: String {
        switch self {
        case .dashboard: "Dashboard"
        case .entries: "Entries"
        case .agent: "Agent"
        case .manage: "Manage"
        case .settings: "Settings"
        }
    }

    var symbol: String {
        switch self {
        case .dashboard: "chart.bar"
        case .entries: "list.bullet.rectangle"
        case .agent: "bubble.left.and.bubble.right"
        case .manage: "square.grid.2x2"
        case .settings: "gearshape"
        }
    }
}

enum AppDeepLink: Equatable {
    case dashboard(month: String?)
    case entry(id: String)
    case account(id: String)
    case group(id: String)
    case agentThread(id: String)
    case settings

    var destination: AppDestination {
        switch self {
        case .dashboard:
            return .dashboard
        case .entry:
            return .entries
        case .account, .group:
            return .manage
        case .agentThread:
            return .agent
        case .settings:
            return .settings
        }
    }

    static func parse(url: URL) -> AppDeepLink? {
        guard url.scheme?.lowercased() == "billhelper" else { return nil }
        let pathParts = url.pathComponents.filter { $0 != "/" }
        switch url.host?.lowercased() {
        case "dashboard":
            return .dashboard(month: URLComponents(url: url, resolvingAgainstBaseURL: false)?
                .queryItems?
                .first(where: { $0.name == "month" })?
                .value)
        case "entries":
            return pathParts.first.map { .entry(id: $0) }
        case "accounts":
            return pathParts.first.map { .account(id: $0) }
        case "groups":
            return pathParts.first.map { .group(id: $0) }
        case "agent":
            if pathParts.count >= 2, pathParts[0] == "threads" {
                return .agentThread(id: pathParts[1])
            }
            return nil
        case "settings":
            return .settings
        default:
            return nil
        }
    }
}

struct AppRootView: View {
    @ObservedObject var composition: AppComposition

    var body: some View {
        Group {
            switch composition.launchPhase {
            case .restoring:
                ProgressView("Restoring session…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(.systemGroupedBackground))
            case .onboarding:
                OnboardingView(composition: composition)
            case .ready:
                AppShellView(composition: composition)
            }
        }
    }
}

struct AppShellView: View {
    @ObservedObject var composition: AppComposition
    @State private var selection: AppDestination = .dashboard
    @State private var pendingDeepLink: AppDeepLink?

    var body: some View {
        TabView(selection: $selection) {
            rootScreen(
                title: AppDestination.dashboard.title,
                destination: .dashboard,
                content: {
                    DashboardRootView(apiClient: composition.apiClient, deepLink: $pendingDeepLink)
                }
            )
            rootScreen(
                title: AppDestination.entries.title,
                destination: .entries,
                content: {
                    EntriesRootView(apiClient: composition.apiClient, deepLink: $pendingDeepLink)
                }
            )
            rootScreen(
                title: AppDestination.agent.title,
                destination: .agent,
                content: {
                    AgentRootView(
                        configuration: composition.configuration,
                        client: .live(apiClient: composition.apiClient, transport: composition.agentRunTransport),
                        deepLink: $pendingDeepLink
                    )
                }
            )
            rootScreen(
                title: AppDestination.manage.title,
                destination: .manage,
                content: {
                    ManageRootView(apiClient: composition.apiClient, deepLink: $pendingDeepLink)
                }
            )
            rootScreen(
                title: AppDestination.settings.title,
                destination: .settings,
                content: {
                    SettingsRootView(composition: composition)
                }
            )
        }
        .tint(.indigo)
        .onOpenURL { url in
            guard let link = AppDeepLink.parse(url: url) else { return }
            selection = link.destination
            pendingDeepLink = link
        }
    }

    private func rootScreen<Content: View>(
        title: String,
        destination: AppDestination,
        @ViewBuilder content: () -> Content
    ) -> some View {
        NavigationStack {
            content()
                .navigationTitle(title)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Text(composition.configuration.environment.displayName)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(.secondary)
                    }
                }
        }
        .tabItem {
            Label(destination.title, systemImage: destination.symbol)
        }
        .tag(destination)
    }
}
