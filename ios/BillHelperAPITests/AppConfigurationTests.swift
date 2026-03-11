import XCTest
@testable import BillHelperApp

@MainActor
final class AppConfigurationTests: XCTestCase {
    func testLiveCompositionRestoresPersistedSessionBeforeWiringClient() async {
        let persisted = AuthSession(
            credential: .bearerToken("secret-token"),
            currentUserName: "Casey"
        )
        let storage = RecordingSessionStorage(session: persisted)

        let composition = AppComposition.live(
            configuration: AppConfiguration(environment: .local, apiBaseURL: AppConfiguration.defaultAPIBaseURL),
            sessionStorage: storage
        )

        await composition.restoreIfNeeded()

        XCTAssertEqual(storage.loadCallCount, 1)
        XCTAssertEqual(composition.sessionStore.currentSession, persisted)
        XCTAssertEqual(composition.launchPhase, .ready)
    }

    func testLiveCompositionContinuesWhenRestoreFails() async {
        let storage = FailingSessionStorage(error: SessionStorageError.unexpectedStatus(errSecParam))

        let composition = AppComposition.live(
            configuration: AppConfiguration(environment: .local, apiBaseURL: AppConfiguration.defaultAPIBaseURL),
            sessionStorage: storage
        )

        await composition.restoreIfNeeded()

        XCTAssertNil(composition.sessionStore.currentSession)
        XCTAssertEqual(composition.launchPhase, .onboarding)
    }

    func testResolvePrefersExplicitEnvironmentValues() {
        let configuration = AppConfiguration.resolve(
            environmentValues: [
                AppConfiguration.environmentKey: "staging",
                AppConfiguration.apiBaseURLKey: "https://staging.example.com/api/v1",
            ],
            infoDictionary: [
                AppConfiguration.environmentKey: "production",
                AppConfiguration.apiBaseURLKey: "https://prod.example.com/api/v1",
            ]
        )

        XCTAssertEqual(configuration.environment, .staging)
        XCTAssertEqual(configuration.apiBaseURL.absoluteString, "https://staging.example.com/api/v1")
    }

    func testResolveFallsBackToInfoDictionaryAndDefaultURL() {
        let configuration = AppConfiguration.resolve(
            environmentValues: [:],
            infoDictionary: [AppConfiguration.environmentKey: "production"]
        )

        XCTAssertEqual(configuration.environment, .production)
        XCTAssertEqual(configuration.apiBaseURL, AppConfiguration.defaultAPIBaseURL)
    }

    func testConnectPersistsPrincipalAndBaseURL() async {
        let storage = RecordingSessionStorage(session: nil)
        let preferences = RecordingAppPreferencesStorage()
        var testedBaseURL: URL?
        var testedSession: AuthSession?
        let composition = AppComposition(
            configuration: AppConfiguration(environment: .local, apiBaseURL: AppConfiguration.defaultAPIBaseURL),
            sessionStore: SessionStore(storage: storage),
            preferencesStorage: preferences,
            connectionTester: { baseURL, session in
                testedBaseURL = baseURL
                testedSession = session
            }
        )

        await composition.connect(baseURLString: "https://example.com/api/v1", principalName: "Morgan")

        XCTAssertEqual(testedBaseURL?.absoluteString, "https://example.com/api/v1")
        XCTAssertEqual(testedSession, AuthSession(credential: .principal(name: "Morgan"), currentUserName: "Morgan"))
        XCTAssertEqual(storage.savedSessions, [AuthSession(credential: .principal(name: "Morgan"), currentUserName: "Morgan")])
        XCTAssertEqual(preferences.savedBaseURLs, [URL(string: "https://example.com/api/v1")!])
        XCTAssertEqual(composition.launchPhase, .ready)
        XCTAssertEqual(composition.activeAPIBaseURL.absoluteString, "https://example.com/api/v1")
        XCTAssertNil(composition.onboardingError)
    }

    func testSignOutClearsSessionAndReturnsToOnboarding() {
        let storage = RecordingSessionStorage(
            session: AuthSession(credential: .principal(name: "Casey"), currentUserName: "Casey")
        )
        let composition = AppComposition(
            configuration: AppConfiguration(environment: .local, apiBaseURL: AppConfiguration.defaultAPIBaseURL),
            sessionStore: SessionStore(storage: storage, initialSession: storage.session),
            preferencesStorage: RecordingAppPreferencesStorage()
        )

        composition.signOut()

        XCTAssertEqual(storage.savedSessions.count, 1)
        XCTAssertNil(storage.savedSessions[0])
        XCTAssertNil(composition.sessionStore.currentSession)
        XCTAssertEqual(composition.launchPhase, .onboarding)
    }
}

private final class RecordingSessionStorage: SessionStorage {
    let session: AuthSession?
    private(set) var loadCallCount = 0
    private(set) var savedSessions: [AuthSession?] = []

    init(session: AuthSession?) {
        self.session = session
    }

    func load() throws -> AuthSession? {
        loadCallCount += 1
        return session
    }

    func save(_ session: AuthSession?) throws {
        savedSessions.append(session)
    }
}

private struct FailingSessionStorage: SessionStorage {
    let error: Error

    func load() throws -> AuthSession? {
        throw error
    }

    func save(_ session: AuthSession?) throws {}
}

private final class RecordingAppPreferencesStorage: AppPreferencesStorage {
    private(set) var savedBaseURLs: [URL?] = []

    func loadBaseURL() -> URL? {
        nil
    }

    func saveBaseURL(_ url: URL?) throws {
        savedBaseURLs.append(url)
    }
}
