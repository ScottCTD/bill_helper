import Foundation
import SwiftUI

enum BillHelperEnvironment: String, CaseIterable, Equatable {
    case local
    case staging
    case production

    var displayName: String { rawValue.capitalized }
}

struct AppConfiguration: Equatable {
    static let environmentKey = "BILL_HELPER_APP_ENVIRONMENT"
    static let apiBaseURLKey = "BILL_HELPER_API_BASE_URL"
    static let defaultAPIBaseURL = URL(string: "http://localhost:8000/api/v1")!

    let environment: BillHelperEnvironment
    let apiBaseURL: URL

    static func resolve(
        environmentValues: [String: String] = ProcessInfo.processInfo.environment,
        infoDictionary: [String: Any] = Bundle.main.infoDictionary ?? [:]
    ) -> AppConfiguration {
        let environmentValue = environmentValues[environmentKey]
            ?? infoDictionary[environmentKey] as? String
            ?? BillHelperEnvironment.local.rawValue
        let environment = BillHelperEnvironment(rawValue: environmentValue.lowercased()) ?? .local

        let apiBaseURLValue = environmentValues[apiBaseURLKey]
            ?? infoDictionary[apiBaseURLKey] as? String
        let apiBaseURL = apiBaseURLValue.flatMap(URL.init(string:)) ?? defaultAPIBaseURL

        return AppConfiguration(environment: environment, apiBaseURL: apiBaseURL)
    }
}

struct AppComposition {
    let configuration: AppConfiguration
    let sessionStore: SessionStore
    let apiClient: APIClient
    let agentRunTransport: AgentRunTransport

    @MainActor @ViewBuilder var dashboardRoot: some View {
        DashboardRootView(apiClient: apiClient)
    }

    @MainActor @ViewBuilder var entriesRoot: some View {
        EntriesRootView(apiClient: apiClient)
    }

    @MainActor @ViewBuilder var agentRoot: some View {
        AgentPlaceholderView(configuration: configuration)
    }

    static func live(
        configuration: AppConfiguration = .resolve(),
        sessionStorage: SessionStorage = KeychainSessionStorage()
    ) -> AppComposition {
        let sessionStore = SessionStore(storage: sessionStorage)
        do {
            try sessionStore.restore()
        } catch {
            NSLog("BillHelper iOS: failed to restore persisted session during app startup: %@", String(describing: error))
        }
        let apiClient = APIClient(baseURL: configuration.apiBaseURL, sessionProvider: sessionStore)
        let agentRunTransport = AgentRunTransport(apiClient: apiClient)
        return AppComposition(
            configuration: configuration,
            sessionStore: sessionStore,
            apiClient: apiClient,
            agentRunTransport: agentRunTransport
        )
    }
}