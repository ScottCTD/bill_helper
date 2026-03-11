import Foundation
import SwiftUI
import os

private let appCompositionLogger = Logger(subsystem: "com.billhelper.ios", category: "AppComposition")

enum AppLaunchPhase: Equatable {
    case restoring
    case onboarding
    case ready
}

@MainActor
final class AppComposition: ObservableObject {
    @Published private(set) var launchPhase: AppLaunchPhase = .restoring
    @Published private(set) var configuration: AppConfiguration
    @Published private(set) var activeAPIBaseURL: URL
    @Published private(set) var sessionStore: SessionStore
    @Published var onboardingError: String?

    private let preferencesStorage: AppPreferencesStorage

    init(
        configuration: AppConfiguration,
        sessionStore: SessionStore,
        preferencesStorage: AppPreferencesStorage
    ) {
        self.configuration = configuration
        self.sessionStore = sessionStore
        self.preferencesStorage = preferencesStorage
        activeAPIBaseURL = preferencesStorage.loadBaseURL() ?? configuration.apiBaseURL
    }

    var apiClient: APIClient {
        APIClient(baseURL: activeAPIBaseURL, sessionProvider: sessionStore)
    }

    var agentRunTransport: AgentRunTransport {
        AgentRunTransport(apiClient: apiClient)
    }

    func restoreIfNeeded() async {
        guard launchPhase == .restoring else { return }
        do {
            try sessionStore.restore()
        } catch {
            appCompositionLogger.error(
                "Failed to restore persisted session during app startup: \(String(describing: error), privacy: .public)"
            )
        }
        launchPhase = sessionStore.currentSession == nil ? .onboarding : .ready
    }

    func connect(baseURLString: String, principalName: String) async {
        let normalizedBaseURL = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        let normalizedPrincipal = principalName.trimmingCharacters(in: .whitespacesAndNewlines)

        guard let baseURL = URL(string: normalizedBaseURL), !normalizedPrincipal.isEmpty else {
            onboardingError = "Enter a valid backend URL and principal name."
            return
        }

        let session = AuthSession(credential: .principal(name: normalizedPrincipal), currentUserName: normalizedPrincipal)
        let testClient = APIClient(baseURL: baseURL, sessionProvider: StaticSessionProvider(currentSession: session))

        do {
            _ = try await testClient.runtimeSettings()
            try preferencesStorage.saveBaseURL(baseURL)
            try sessionStore.save(session)
            activeAPIBaseURL = baseURL
            onboardingError = nil
            launchPhase = .ready
        } catch {
            onboardingError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    func updateConnection(baseURLString: String, principalName: String) async {
        await connect(baseURLString: baseURLString, principalName: principalName)
    }

    func signOut() {
        do {
            try sessionStore.clear()
            onboardingError = nil
            launchPhase = .onboarding
        } catch {
            onboardingError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    static func live(
        configuration: AppConfiguration = .resolve(),
        sessionStorage: SessionStorage = KeychainSessionStorage(),
        preferencesStorage: AppPreferencesStorage = UserDefaultsAppPreferencesStorage()
    ) -> AppComposition {
        AppComposition(
            configuration: configuration,
            sessionStore: SessionStore(storage: sessionStorage),
            preferencesStorage: preferencesStorage
        )
    }
}
