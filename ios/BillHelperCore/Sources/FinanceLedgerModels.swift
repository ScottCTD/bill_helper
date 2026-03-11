import Foundation

enum EntryKind: String, Codable, Equatable, Hashable, Sendable, CaseIterable {
    case expense = "EXPENSE"
    case income = "INCOME"
    case transfer = "TRANSFER"
}

enum GroupType: String, Codable, Equatable, Hashable, Sendable, CaseIterable {
    case bundle = "BUNDLE"
    case split = "SPLIT"
    case recurring = "RECURRING"
}

enum GroupMemberRole: String, Codable, Equatable, Hashable, Sendable, CaseIterable {
    case parent = "PARENT"
    case child = "CHILD"
}

struct EntryGroupRef: Codable, Equatable, Hashable, Sendable {
    let id: String
    let name: String
    let groupType: GroupType
}

struct Account: Codable, Equatable, Hashable, Sendable {
    let id: String
    let ownerUserId: String?
    let name: String
    let markdownBody: String?
    let currencyCode: String
    let isActive: Bool
    let createdAt: String
    let updatedAt: String
}

struct AccountCreatePayload: Encodable, Equatable, Sendable {
    var ownerUserId: String?
    var name: String
    var markdownBody: String?
    var currencyCode: String
    var isActive: Bool = true
}

struct AccountUpdatePayload: Encodable, Equatable, Sendable {
    var ownerUserId: String?
    var name: String?
    var markdownBody: String?
    var currencyCode: String?
    var isActive: Bool?
}

struct Snapshot: Codable, Equatable, Hashable, Sendable {
    let id: String
    let accountId: String
    let snapshotAt: String
    let balanceMinor: Int
    let note: String?
    let createdAt: String
}

struct SnapshotSummary: Codable, Equatable, Hashable, Sendable {
    let id: String
    let snapshotAt: String
    let balanceMinor: Int
    let note: String?
}

struct SnapshotCreatePayload: Encodable, Equatable, Sendable {
    var snapshotAt: String
    var balanceMinor: Int
    var note: String?
}

struct ReconciliationInterval: Codable, Equatable, Hashable, Sendable {
    let startSnapshot: SnapshotSummary
    let endSnapshot: SnapshotSummary?
    let isOpen: Bool
    let trackedChangeMinor: Int
    let bankChangeMinor: Int?
    let deltaMinor: Int?
    let entryCount: Int
}

struct Reconciliation: Codable, Equatable, Hashable, Sendable {
    let accountId: String
    let accountName: String
    let currencyCode: String
    let asOf: String
    let intervals: [ReconciliationInterval]
}

struct Entry: Codable, Equatable, Hashable, Sendable {
    let id: String
    let accountId: String?
    let kind: EntryKind
    let occurredAt: String
    let name: String
    let amountMinor: Int
    let currencyCode: String
    let fromEntityId: String?
    let toEntityId: String?
    let ownerUserId: String?
    let fromEntity: String?
    let fromEntityMissing: Bool
    let toEntity: String?
    let toEntityMissing: Bool
    let owner: String?
    let markdownBody: String?
    let createdAt: String
    let updatedAt: String
    let tags: [Tag]
    let directGroup: EntryGroupRef?
    let directGroupMemberRole: GroupMemberRole?
    let groupPath: [EntryGroupRef]
}

typealias EntryDetail = Entry

struct EntryListResponse: Codable, Equatable, Sendable {
    let items: [Entry]
    let total: Int
    let limit: Int
    let offset: Int
}

struct EntryListQuery: Equatable, Sendable {
    var startDate: String?
    var endDate: String?
    var kind: EntryKind?
    var tag: String?
    var currency: String?
    var source: String?
    var accountId: String?
    var filterGroupId: String?
    var limit: Int?
    var offset: Int?

    func queryItems() -> [URLQueryItem] {
        var items: [URLQueryItem] = []
        if let startDate, !startDate.isEmpty {
            items.append(URLQueryItem(name: "start_date", value: startDate))
        }
        if let endDate, !endDate.isEmpty {
            items.append(URLQueryItem(name: "end_date", value: endDate))
        }
        if let kind {
            items.append(URLQueryItem(name: "kind", value: kind.rawValue))
        }
        if let tag, !tag.isEmpty {
            items.append(URLQueryItem(name: "tag", value: tag))
        }
        if let currency, !currency.isEmpty {
            items.append(URLQueryItem(name: "currency", value: currency))
        }
        if let source, !source.isEmpty {
            items.append(URLQueryItem(name: "source", value: source))
        }
        if let accountId, !accountId.isEmpty {
            items.append(URLQueryItem(name: "account_id", value: accountId))
        }
        if let filterGroupId, !filterGroupId.isEmpty {
            items.append(URLQueryItem(name: "filter_group_id", value: filterGroupId))
        }
        if let limit {
            items.append(URLQueryItem(name: "limit", value: String(limit)))
        }
        if let offset {
            items.append(URLQueryItem(name: "offset", value: String(offset)))
        }
        return items
    }
}

struct EntryCreatePayload: Encodable, Equatable, Sendable {
    var accountId: String?
    var kind: EntryKind
    var occurredAt: String
    var name: String
    var amountMinor: Int
    var currencyCode: String
    var fromEntityId: String?
    var toEntityId: String?
    var ownerUserId: String?
    var fromEntity: String?
    var toEntity: String?
    var owner: String?
    var markdownBody: String?
    var tags: [String]
    var directGroupId: String?
    var directGroupMemberRole: GroupMemberRole?
}

struct EntryUpdatePayload: Encodable, Equatable, Sendable {
    var accountId: String?
    var kind: EntryKind?
    var occurredAt: String?
    var name: String?
    var amountMinor: Int?
    var currencyCode: String?
    var fromEntityId: String?
    var toEntityId: String?
    var ownerUserId: String?
    var fromEntity: String?
    var toEntity: String?
    var owner: String?
    var markdownBody: String?
    var tags: [String]?
    var directGroupId: String?
    var directGroupMemberRole: GroupMemberRole?
}

enum GroupMemberTarget: Equatable, Hashable, Sendable {
    case entry(entryId: String)
    case childGroup(groupId: String)
}

extension GroupMemberTarget: Codable {
    private enum CodingKeys: String, CodingKey {
        case targetType
        case entryId
        case groupId
    }

    private enum TargetType: String, Codable {
        case entry
        case childGroup = "child_group"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(TargetType.self, forKey: .targetType)
        switch type {
        case .entry:
            self = .entry(entryId: try container.decode(String.self, forKey: .entryId))
        case .childGroup:
            self = .childGroup(groupId: try container.decode(String.self, forKey: .groupId))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .entry(let entryId):
            try container.encode(TargetType.entry, forKey: .targetType)
            try container.encode(entryId, forKey: .entryId)
        case .childGroup(let groupId):
            try container.encode(TargetType.childGroup, forKey: .targetType)
            try container.encode(groupId, forKey: .groupId)
        }
    }
}

struct GroupMemberCreatePayload: Codable, Equatable, Hashable, Sendable {
    var target: GroupMemberTarget
    var memberRole: GroupMemberRole?
}

struct GroupCreatePayload: Encodable, Equatable, Sendable {
    var name: String
    var groupType: GroupType
}

struct GroupUpdatePayload: Encodable, Equatable, Sendable {
    var name: String
}

struct GroupNode: Codable, Equatable, Hashable, Sendable {
    let graphId: String
    let membershipId: String
    let subjectId: String
    let nodeType: String
    let name: String
    let memberRole: GroupMemberRole?
    let representativeOccurredAt: String?
    let kind: EntryKind?
    let amountMinor: Int?
    let currencyCode: String?
    let occurredAt: String?
    let groupType: GroupType?
    let descendantEntryCount: Int?
    let firstOccurredAt: String?
    let lastOccurredAt: String?
}

struct GroupEdge: Codable, Equatable, Hashable, Sendable {
    let id: String
    let sourceGraphId: String
    let targetGraphId: String
    let groupType: GroupType
}

struct GroupGraph: Codable, Equatable, Hashable, Sendable {
    let id: String
    let name: String
    let groupType: GroupType
    let parentGroupId: String?
    let directMemberCount: Int
    let directEntryCount: Int
    let directChildGroupCount: Int
    let descendantEntryCount: Int
    let firstOccurredAt: String?
    let lastOccurredAt: String?
    let nodes: [GroupNode]
    let edges: [GroupEdge]
}

struct GroupSummary: Codable, Equatable, Hashable, Sendable {
    let id: String
    let name: String
    let groupType: GroupType
    let parentGroupId: String?
    let directMemberCount: Int
    let directEntryCount: Int
    let directChildGroupCount: Int
    let descendantEntryCount: Int
    let firstOccurredAt: String?
    let lastOccurredAt: String?
}
