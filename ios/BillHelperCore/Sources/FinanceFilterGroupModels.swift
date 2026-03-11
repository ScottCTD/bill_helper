import Foundation

enum FilterRuleField: String, Codable, Equatable, Hashable, Sendable, CaseIterable {
    case entryKind = "entry_kind"
    case tags
    case isInternalTransfer = "is_internal_transfer"
}

enum FilterRuleConditionOperator: String, Codable, Equatable, Hashable, Sendable, CaseIterable {
    case `is`
    case hasAny = "has_any"
    case hasNone = "has_none"
}

enum FilterRuleLogicalOperator: String, Codable, Equatable, Hashable, Sendable, CaseIterable {
    case and = "AND"
    case or = "OR"
}

enum FilterRuleValue: Equatable, Hashable, Sendable {
    case string(String)
    case boolean(Bool)
    case strings([String])
}

extension FilterRuleValue: Codable {
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let value = try? container.decode(Bool.self) {
            self = .boolean(value)
            return
        }
        if let value = try? container.decode([String].self) {
            self = .strings(value)
            return
        }
        self = .string(try container.decode(String.self))
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .boolean(let value):
            try container.encode(value)
        case .strings(let value):
            try container.encode(value)
        }
    }
}

struct FilterRuleCondition: Codable, Equatable, Hashable, Sendable {
    let type: String
    var field: FilterRuleField
    var `operator`: FilterRuleConditionOperator
    var value: FilterRuleValue

    init(field: FilterRuleField, operator: FilterRuleConditionOperator, value: FilterRuleValue) {
        type = "condition"
        self.field = field
        self.operator = `operator`
        self.value = value
    }
}

struct FilterRuleGroup: Codable, Equatable, Hashable, Sendable {
    let type: String
    var `operator`: FilterRuleLogicalOperator
    var children: [FilterRuleNode]

    init(operator: FilterRuleLogicalOperator, children: [FilterRuleNode]) {
        type = "group"
        self.operator = `operator`
        self.children = children
    }
}

enum FilterRuleNode: Equatable, Hashable, Sendable {
    case condition(FilterRuleCondition)
    case group(FilterRuleGroup)
}

extension FilterRuleNode: Codable {
    private enum CodingKeys: String, CodingKey {
        case type
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .type)
        switch type {
        case "condition":
            self = .condition(try FilterRuleCondition(from: decoder))
        case "group":
            self = .group(try FilterRuleGroup(from: decoder))
        default:
            throw DecodingError.dataCorruptedError(forKey: .type, in: container, debugDescription: "Unsupported filter rule node type.")
        }
    }

    func encode(to encoder: Encoder) throws {
        switch self {
        case .condition(let condition):
            try condition.encode(to: encoder)
        case .group(let group):
            try group.encode(to: encoder)
        }
    }
}

struct FilterGroupRule: Codable, Equatable, Hashable, Sendable {
    var include: FilterRuleGroup
    var exclude: FilterRuleGroup?
}

struct FilterGroup: Codable, Equatable, Hashable, Sendable {
    let id: String
    let key: String
    let name: String
    let description: String?
    let color: String?
    let isDefault: Bool
    let position: Int
    let rule: FilterGroupRule
    let ruleSummary: String
    let createdAt: String
    let updatedAt: String
}

struct FilterGroupCreatePayload: Encodable, Equatable, Sendable {
    var name: String
    var description: String?
    var color: String?
    var rule: FilterGroupRule
}

struct FilterGroupUpdatePayload: Encodable, Equatable, Sendable {
    var name: String?
    var description: String?
    var color: String?
    var rule: FilterGroupRule?
}
