import SwiftUI

enum AppDestination: String, Hashable, CaseIterable {
    case dashboard
    case entries
    case agent

    var title: String {
        switch self {
        case .dashboard: "Dashboard"
        case .entries: "Entries"
        case .agent: "Agent"
        }
    }

    var symbol: String {
        switch self {
        case .dashboard: "chart.bar"
        case .entries: "list.bullet.rectangle"
        case .agent: "bubble.left.and.bubble.right"
        }
    }
}

struct AppShellView: View {
    let composition: AppComposition

    var body: some View {
        TabView {
            rootScreen(
                title: AppDestination.dashboard.title,
                destination: .dashboard,
                content: { composition.dashboardRoot }
            )
            rootScreen(
                title: AppDestination.entries.title,
                destination: .entries,
                content: { composition.entriesRoot }
            )
            rootScreen(
                title: AppDestination.agent.title,
                destination: .agent,
                content: { composition.agentRoot }
            )
        }
        .tint(.indigo)
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