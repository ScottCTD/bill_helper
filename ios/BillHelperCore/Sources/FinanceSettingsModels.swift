import Foundation

struct RuntimeSettingsOverrides: Codable, Equatable, Sendable {
    let userMemory: [String]?
    let defaultCurrencyCode: String?
    let dashboardCurrencyCode: String?
    let agentModel: String?
    let availableAgentModels: [String]?
    let agentMaxSteps: Int?
    let agentBulkMaxConcurrentThreads: Int?
    let agentRetryMaxAttempts: Int?
    let agentRetryInitialWaitSeconds: Double?
    let agentRetryMaxWaitSeconds: Double?
    let agentRetryBackoffMultiplier: Double?
    let agentMaxImageSizeBytes: Int?
    let agentMaxImagesPerMessage: Int?
    let agentBaseURL: String?
    let agentApiKeyConfigured: Bool
}

struct RuntimeSettings: Codable, Equatable, Sendable {
    let currentUserName: String
    let userMemory: [String]?
    let defaultCurrencyCode: String
    let dashboardCurrencyCode: String
    let agentModel: String
    let availableAgentModels: [String]
    let agentMaxSteps: Int
    let agentBulkMaxConcurrentThreads: Int
    let agentRetryMaxAttempts: Int
    let agentRetryInitialWaitSeconds: Double
    let agentRetryMaxWaitSeconds: Double
    let agentRetryBackoffMultiplier: Double
    let agentMaxImageSizeBytes: Int
    let agentMaxImagesPerMessage: Int
    let agentBaseURL: String?
    let agentApiKeyConfigured: Bool
    let overrides: RuntimeSettingsOverrides
}

struct RuntimeSettingsUpdatePayload: Encodable, Equatable, Sendable {
    var userMemory: [String]?
    var defaultCurrencyCode: String?
    var dashboardCurrencyCode: String?
    var agentModel: String?
    var availableAgentModels: [String]?
    var agentMaxSteps: Int?
    var agentBulkMaxConcurrentThreads: Int?
    var agentRetryMaxAttempts: Int?
    var agentRetryInitialWaitSeconds: Double?
    var agentRetryMaxWaitSeconds: Double?
    var agentRetryBackoffMultiplier: Double?
    var agentMaxImageSizeBytes: Int?
    var agentMaxImagesPerMessage: Int?
    var agentBaseURL: String?
    var agentApiKey: String?
}
