import Foundation

enum JSONValue: Codable, Equatable, Sendable {
    case string(String)
    case number(Double)
    case boolean(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .boolean(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value.")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .boolean(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }
}

enum AgentMessageRole: String, Codable, Equatable, Sendable {
    case user
    case assistant
    case system
}

enum AgentRunStatus: String, Codable, Equatable, Sendable {
    case running
    case completed
    case failed

    var isTerminal: Bool {
        self != .running
    }
}

enum AgentToolCallStatus: String, Codable, Equatable, Sendable {
    case queued
    case running
    case ok
    case error
    case cancelled
}

enum AgentRunEventType: String, Codable, Equatable, Sendable {
    case runStarted = "run_started"
    case reasoningUpdate = "reasoning_update"
    case toolCallQueued = "tool_call_queued"
    case toolCallStarted = "tool_call_started"
    case toolCallCompleted = "tool_call_completed"
    case toolCallFailed = "tool_call_failed"
    case toolCallCancelled = "tool_call_cancelled"
    case runCompleted = "run_completed"
    case runFailed = "run_failed"
}

enum AgentRunEventSource: String, Codable, Equatable, Sendable {
    case modelReasoning = "model_reasoning"
    case assistantContent = "assistant_content"
    case toolCall = "tool_call"
}

enum AgentChangeType: String, Codable, Equatable, Sendable {
    case createEntry = "create_entry"
    case updateEntry = "update_entry"
    case deleteEntry = "delete_entry"
    case createAccount = "create_account"
    case updateAccount = "update_account"
    case deleteAccount = "delete_account"
    case createGroup = "create_group"
    case updateGroup = "update_group"
    case deleteGroup = "delete_group"
    case createGroupMember = "create_group_member"
    case deleteGroupMember = "delete_group_member"
    case createTag = "create_tag"
    case updateTag = "update_tag"
    case deleteTag = "delete_tag"
    case createEntity = "create_entity"
    case updateEntity = "update_entity"
    case deleteEntity = "delete_entity"
}

enum AgentChangeStatus: String, Codable, Equatable, Sendable {
    case pendingReview = "PENDING_REVIEW"
    case approved = "APPROVED"
    case rejected = "REJECTED"
    case applied = "APPLIED"
    case applyFailed = "APPLY_FAILED"
}

enum AgentReviewActionType: String, Codable, Equatable, Sendable {
    case approve
    case reject
}

struct AgentThread: Codable, Equatable, Sendable {
    let id: String
    let title: String?
    let createdAt: String
    let updatedAt: String
}

struct AgentThreadSummary: Codable, Equatable, Hashable, Sendable {
    let id: String
    let title: String?
    let createdAt: String
    let updatedAt: String
    let lastMessagePreview: String?
    let pendingChangeCount: Int
    let hasRunningRun: Bool
}

struct AgentMessageAttachment: Codable, Equatable, Sendable {
    let id: String
    let messageId: String
    let mimeType: String
    let filePath: String
    let attachmentURL: String
    let createdAt: String
}

struct AgentMessage: Codable, Equatable, Sendable {
    let id: String
    let threadId: String
    let role: AgentMessageRole
    let contentMarkdown: String
    let createdAt: String
    let attachments: [AgentMessageAttachment]
}

struct AgentToolCall: Codable, Equatable, Identifiable, Sendable {
    let id: String
    let runId: String
    let llmToolCallId: String?
    let toolName: String
    let inputJson: [String: JSONValue]?
    let outputJson: [String: JSONValue]?
    let outputText: String?
    let hasFullPayload: Bool
    let status: AgentToolCallStatus
    let createdAt: String
    let startedAt: String?
    let completedAt: String?
}

struct AgentRunEvent: Codable, Equatable, Sendable {
    let id: String
    let runId: String
    let sequenceIndex: Int
    let eventType: AgentRunEventType
    let source: AgentRunEventSource?
    let message: String?
    let toolCallId: String?
    let createdAt: String
}

struct AgentReviewAction: Codable, Equatable, Sendable {
    let id: String
    let changeItemId: String
    let action: AgentReviewActionType
    let actor: String
    let note: String?
    let createdAt: String
}

struct AgentChangeItem: Codable, Equatable, Sendable {
    let id: String
    let runId: String
    let changeType: AgentChangeType
    let payloadJson: [String: JSONValue]
    let rationaleText: String
    let status: AgentChangeStatus
    let reviewNote: String?
    let appliedResourceType: String?
    let appliedResourceId: String?
    let createdAt: String
    let updatedAt: String
    let reviewActions: [AgentReviewAction]
}

struct AgentRun: Codable, Equatable, Sendable {
    let id: String
    let threadId: String
    let userMessageId: String
    let assistantMessageId: String?
    let terminalAssistantReply: String?
    let status: AgentRunStatus
    let modelName: String
    let surface: String
    let replySurface: String
    let contextTokens: Int?
    let inputTokens: Int?
    let outputTokens: Int?
    let cacheReadTokens: Int?
    let cacheWriteTokens: Int?
    let inputCostUsd: Double?
    let outputCostUsd: Double?
    let totalCostUsd: Double?
    let errorText: String?
    let createdAt: String
    let completedAt: String?
    let events: [AgentRunEvent]
    let toolCalls: [AgentToolCall]
    let changeItems: [AgentChangeItem]
}

struct AgentThreadDetail: Codable, Equatable, Sendable {
    let thread: AgentThread
    let messages: [AgentMessage]
    let runs: [AgentRun]
    let configuredModelName: String
    let currentContextTokens: Int?
}

enum AgentStreamEvent: Equatable, Sendable {
    case reasoningDelta(runId: String, delta: String)
    case textDelta(runId: String, delta: String)
    case runEvent(runId: String, event: AgentRunEvent, toolCall: AgentToolCall?)

    var runId: String {
        switch self {
        case .reasoningDelta(let runId, _), .textDelta(let runId, _), .runEvent(let runId, _, _):
            runId
        }
    }
}

extension AgentStreamEvent: Decodable {
    private enum CodingKeys: String, CodingKey {
        case type
        case runId
        case delta
        case event
        case toolCall
    }

    private enum Kind: String, Decodable {
        case reasoningDelta = "reasoning_delta"
        case textDelta = "text_delta"
        case runEvent = "run_event"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let kind = try container.decode(Kind.self, forKey: .type)
        let runId = try container.decode(String.self, forKey: .runId)
        switch kind {
        case .reasoningDelta:
            self = .reasoningDelta(runId: runId, delta: try container.decode(String.self, forKey: .delta))
        case .textDelta:
            self = .textDelta(runId: runId, delta: try container.decode(String.self, forKey: .delta))
        case .runEvent:
            self = .runEvent(
                runId: runId,
                event: try container.decode(AgentRunEvent.self, forKey: .event),
                toolCall: try container.decodeIfPresent(AgentToolCall.self, forKey: .toolCall)
            )
        }
    }
}
