import Foundation

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
