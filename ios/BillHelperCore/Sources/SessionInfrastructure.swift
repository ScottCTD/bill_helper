import Foundation
import Security

enum SessionCredential: Codable, Equatable {
    case principal(name: String)
    case bearerToken(String)

    private enum CodingKeys: String, CodingKey {
        case kind
        case value
    }

    private enum Kind: String, Codable {
        case principal
        case bearerToken
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let kind = try container.decode(Kind.self, forKey: .kind)
        let value = try container.decode(String.self, forKey: .value)
        switch kind {
        case .principal:
            self = .principal(name: value)
        case .bearerToken:
            self = .bearerToken(value)
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .principal(let name):
            try container.encode(Kind.principal, forKey: .kind)
            try container.encode(name, forKey: .value)
        case .bearerToken(let token):
            try container.encode(Kind.bearerToken, forKey: .kind)
            try container.encode(token, forKey: .value)
        }
    }
}

struct AuthSession: Codable, Equatable {
    let credential: SessionCredential
    let currentUserName: String?
}

protocol SessionProviding {
    var currentSession: AuthSession? { get }
}

struct StaticSessionProvider: SessionProviding {
    let currentSession: AuthSession?
}

protocol SessionStorage {
    func load() throws -> AuthSession?
    func save(_ session: AuthSession?) throws
}

enum SessionStorageError: Error, Equatable {
    case unexpectedStatus(OSStatus)
}

final class KeychainSessionStorage: SessionStorage {
    private let service: String
    private let account: String
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(service: String = "com.billhelper.ios.session", account: String = "default") {
        self.service = service
        self.account = account
    }

    func load() throws -> AuthSession? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound {
            return nil
        }
        guard status == errSecSuccess else {
            throw SessionStorageError.unexpectedStatus(status)
        }
        guard let data = result as? Data else {
            return nil
        }
        return try decoder.decode(AuthSession.self, from: data)
    }

    func save(_ session: AuthSession?) throws {
        if let session {
            let data = try encoder.encode(session)
            let status = SecItemCopyMatching(baseQuery() as CFDictionary, nil)
            switch status {
            case errSecSuccess:
                let attributes = [kSecValueData as String: data]
                let updateStatus = SecItemUpdate(baseQuery() as CFDictionary, attributes as CFDictionary)
                guard updateStatus == errSecSuccess else {
                    throw SessionStorageError.unexpectedStatus(updateStatus)
                }
            case errSecItemNotFound:
                var query = baseQuery()
                query[kSecValueData as String] = data
                let addStatus = SecItemAdd(query as CFDictionary, nil)
                guard addStatus == errSecSuccess else {
                    throw SessionStorageError.unexpectedStatus(addStatus)
                }
            default:
                throw SessionStorageError.unexpectedStatus(status)
            }
        } else {
            let status = SecItemDelete(baseQuery() as CFDictionary)
            guard status == errSecSuccess || status == errSecItemNotFound else {
                throw SessionStorageError.unexpectedStatus(status)
            }
        }
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}

final class InMemorySessionStorage: SessionStorage {
    private var storedSession: AuthSession?

    init(session: AuthSession? = nil) {
        storedSession = session
    }

    func load() throws -> AuthSession? {
        storedSession
    }

    func save(_ session: AuthSession?) throws {
        storedSession = session
    }
}

protocol AppPreferencesStorage {
    func loadBaseURL() -> URL?
    func saveBaseURL(_ url: URL?) throws
}

enum AppPreferencesError: Error, Equatable {
    case invalidURLString
}

final class UserDefaultsAppPreferencesStorage: AppPreferencesStorage {
    private let defaults: UserDefaults
    private let baseURLKey: String

    init(defaults: UserDefaults = .standard, baseURLKey: String = "com.billhelper.ios.apiBaseURL") {
        self.defaults = defaults
        self.baseURLKey = baseURLKey
    }

    func loadBaseURL() -> URL? {
        guard let rawValue = defaults.string(forKey: baseURLKey), !rawValue.isEmpty else {
            return nil
        }
        return URL(string: rawValue)
    }

    func saveBaseURL(_ url: URL?) throws {
        if let url {
            defaults.set(url.absoluteString, forKey: baseURLKey)
        } else {
            defaults.removeObject(forKey: baseURLKey)
        }
    }
}

final class SessionStore: ObservableObject, SessionProviding, @unchecked Sendable {
    private let storage: SessionStorage
    @Published private(set) var currentSession: AuthSession?

    init(storage: SessionStorage, initialSession: AuthSession? = nil) {
        self.storage = storage
        currentSession = initialSession
    }

    func restore() throws {
        currentSession = try storage.load()
    }

    func save(_ session: AuthSession) throws {
        try storage.save(session)
        currentSession = session
    }

    func clear() throws {
        try storage.save(nil)
        currentSession = nil
    }
}
