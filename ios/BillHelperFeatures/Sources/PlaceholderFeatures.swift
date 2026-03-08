import SwiftUI

private struct ShellCard<Content: View>: View {
    let title: String
    let subtitle: String
    let symbol: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label(title, systemImage: symbol)
                .font(.title3.weight(.semibold))
            Text(subtitle)
                .font(.body)
                .foregroundStyle(.secondary)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
    }
}

private struct ConfigSummaryView: View {
    let configuration: AppConfiguration

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(configuration.environment.displayName, systemImage: "globe")
            Label(configuration.apiBaseURL.absoluteString, systemImage: "network")
                .lineLimit(2)
                .truncationMode(.middle)
        }
        .font(.footnote)
        .foregroundStyle(.secondary)
    }
}

struct DashboardPlaceholderView: View {
    let configuration: AppConfiguration

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                ShellCard(
                    title: "Dashboard shell",
                    subtitle: "Wave 1 scaffolding is ready for the dashboard summary module to plug into this navigation root.",
                    symbol: "chart.bar.fill"
                ) {
                    ConfigSummaryView(configuration: configuration)
                }
            }
            .padding(20)
        }
        .background(Color(.systemGroupedBackground))
    }
}

struct EntriesPlaceholderView: View {
    let configuration: AppConfiguration

    var body: some View {
        List {
            Section("Ready for MVP") {
                Label("Entries list surface", systemImage: "list.bullet.rectangle.portrait")
                Label("Loading / empty / error states", systemImage: "circle.dotted.circle")
            }

            Section("Shared app context") {
                ConfigSummaryView(configuration: configuration)
            }
        }
        .listStyle(.insetGrouped)
    }
}

struct AgentPlaceholderView: View {
    let configuration: AppConfiguration
    let client: AgentFeatureClient

    var body: some View {
        AgentRootView(configuration: configuration, client: client)
    }
}