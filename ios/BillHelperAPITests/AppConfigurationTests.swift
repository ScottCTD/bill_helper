import XCTest
@testable import BillHelperApp

final class AppConfigurationTests: XCTestCase {
    func testLiveCompositionRestoresPersistedSessionBeforeWiringClient() {
        let persisted = AuthSession(
            credential: .bearerToken("secret-token"),
            currentUserName: "Casey"
        )
        let storage = RecordingSessionStorage(session: persisted)

        let composition = AppComposition.live(
            configuration: AppConfiguration(environment: .local, apiBaseURL: AppConfiguration.defaultAPIBaseURL),
            sessionStorage: storage
        )

        XCTAssertEqual(storage.loadCallCount, 1)
        XCTAssertEqual(composition.sessionStore.currentSession, persisted)
    }

    func testLiveCompositionContinuesWhenRestoreFails() {
        let storage = FailingSessionStorage(error: SessionStorageError.unexpectedStatus(errSecParam))

        let composition = AppComposition.live(
            configuration: AppConfiguration(environment: .local, apiBaseURL: AppConfiguration.defaultAPIBaseURL),
            sessionStorage: storage
        )

        XCTAssertNil(composition.sessionStore.currentSession)
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
}

private final class RecordingSessionStorage: SessionStorage {
    private let session: AuthSession?
    private(set) var loadCallCount = 0

    init(session: AuthSession?) {
        self.session = session
    }

    func load() throws -> AuthSession? {
        loadCallCount += 1
        return session
    }

    func save(_ session: AuthSession?) throws {}
}

private struct FailingSessionStorage: SessionStorage {
    let error: Error

    func load() throws -> AuthSession? {
        throw error
    }

    func save(_ session: AuthSession?) throws {}
}