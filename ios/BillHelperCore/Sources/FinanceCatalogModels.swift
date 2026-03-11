import Foundation

struct Tag: Codable, Equatable, Hashable, Sendable {
    let id: Int
    let name: String
    let color: String?
    let description: String?
    let type: String?
    let entryCount: Int?
}

struct TagCreatePayload: Encodable, Equatable, Sendable {
    var name: String
    var color: String?
    var description: String?
    var type: String?
}

struct TagUpdatePayload: Encodable, Equatable, Sendable {
    var name: String?
    var color: String?
    var description: String?
    var type: String?
}

struct Entity: Codable, Equatable, Hashable, Sendable {
    let id: String
    let name: String
    let category: String?
    let isAccount: Bool
    let fromCount: Int?
    let toCount: Int?
    let accountCount: Int?
    let entryCount: Int?
    let netAmountMinor: Int?
    let netAmountCurrencyCode: String?
    let netAmountMixedCurrencies: Bool
}

struct EntityCreatePayload: Encodable, Equatable, Sendable {
    var name: String
    var category: String?
}

struct EntityUpdatePayload: Encodable, Equatable, Sendable {
    var name: String?
    var category: String?
}

struct User: Codable, Equatable, Hashable, Sendable {
    let id: String
    let name: String
    let isAdmin: Bool
    let isCurrentUser: Bool
    let accountCount: Int?
    let entryCount: Int?
}

struct UserCreatePayload: Encodable, Equatable, Sendable {
    var name: String
}

struct UserUpdatePayload: Encodable, Equatable, Sendable {
    var name: String?
    var isAdmin: Bool?
}

struct Currency: Codable, Equatable, Hashable, Sendable {
    let code: String
    let name: String
    let entryCount: Int
    let isPlaceholder: Bool
}

struct Taxonomy: Codable, Equatable, Hashable, Sendable {
    let id: String
    let key: String
    let appliesTo: String
    let cardinality: String
    let displayName: String
}

struct TaxonomyTerm: Codable, Equatable, Hashable, Sendable {
    let id: String
    let taxonomyId: String
    let name: String
    let normalizedName: String
    let description: String?
    let usageCount: Int
}

struct TaxonomyTermCreatePayload: Encodable, Equatable, Sendable {
    var name: String
    var description: String?
}

struct TaxonomyTermUpdatePayload: Encodable, Equatable, Sendable {
    var name: String?
    var description: String?
}
