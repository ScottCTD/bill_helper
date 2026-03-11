import Foundation

extension APIClient {
    func dashboard(month: String) async throws -> Dashboard {
        try await perform(path: "/dashboard", queryItems: [URLQueryItem(name: "month", value: month)])
    }

    func dashboardTimeline() async throws -> DashboardTimeline {
        try await perform(path: "/dashboard/timeline")
    }

    func listEntries(query: EntryListQuery = EntryListQuery()) async throws -> EntryListResponse {
        try await perform(path: "/entries", queryItems: query.queryItems())
    }

    func entry(id: String) async throws -> EntryDetail {
        try await perform(path: "/entries/\(id)")
    }

    func createEntry(_ payload: EntryCreatePayload) async throws -> EntryDetail {
        try await perform(path: "/entries", method: "POST", body: try encoder.encode(payload))
    }

    func updateEntry(id: String, payload: EntryUpdatePayload) async throws -> EntryDetail {
        try await perform(path: "/entries/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }

    func deleteEntry(id: String) async throws {
        _ = try await performWithoutResponse(path: "/entries/\(id)", method: "DELETE")
    }

    func listAccounts() async throws -> [Account] {
        try await perform(path: "/accounts")
    }

    func createAccount(_ payload: AccountCreatePayload) async throws -> Account {
        try await perform(path: "/accounts", method: "POST", body: try encoder.encode(payload))
    }

    func updateAccount(id: String, payload: AccountUpdatePayload) async throws -> Account {
        try await perform(path: "/accounts/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }

    func deleteAccount(id: String) async throws {
        _ = try await performWithoutResponse(path: "/accounts/\(id)", method: "DELETE")
    }

    func listAccountSnapshots(accountID: String) async throws -> [Snapshot] {
        try await perform(path: "/accounts/\(accountID)/snapshots")
    }

    func createAccountSnapshot(accountID: String, payload: SnapshotCreatePayload) async throws -> Snapshot {
        try await perform(path: "/accounts/\(accountID)/snapshots", method: "POST", body: try encoder.encode(payload))
    }

    func deleteAccountSnapshot(accountID: String, snapshotID: String) async throws {
        _ = try await performWithoutResponse(path: "/accounts/\(accountID)/snapshots/\(snapshotID)", method: "DELETE")
    }

    func accountReconciliation(accountID: String) async throws -> Reconciliation {
        try await perform(path: "/accounts/\(accountID)/reconciliation")
    }

    func listGroups() async throws -> [GroupSummary] {
        try await perform(path: "/groups")
    }

    func group(id: String) async throws -> GroupGraph {
        try await perform(path: "/groups/\(id)")
    }

    func createGroup(_ payload: GroupCreatePayload) async throws -> GroupSummary {
        try await perform(path: "/groups", method: "POST", body: try encoder.encode(payload))
    }

    func updateGroup(id: String, payload: GroupUpdatePayload) async throws -> GroupSummary {
        try await perform(path: "/groups/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }

    func deleteGroup(id: String) async throws {
        _ = try await performWithoutResponse(path: "/groups/\(id)", method: "DELETE")
    }

    func addGroupMember(groupID: String, payload: GroupMemberCreatePayload) async throws -> GroupGraph {
        try await perform(path: "/groups/\(groupID)/members", method: "POST", body: try encoder.encode(payload))
    }

    func deleteGroupMember(groupID: String, membershipID: String) async throws {
        _ = try await performWithoutResponse(path: "/groups/\(groupID)/members/\(membershipID)", method: "DELETE")
    }

    func listFilterGroups() async throws -> [FilterGroup] {
        try await perform(path: "/filter-groups")
    }

    func createFilterGroup(_ payload: FilterGroupCreatePayload) async throws -> FilterGroup {
        try await perform(path: "/filter-groups", method: "POST", body: try encoder.encode(payload))
    }

    func updateFilterGroup(id: String, payload: FilterGroupUpdatePayload) async throws -> FilterGroup {
        try await perform(path: "/filter-groups/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }

    func deleteFilterGroup(id: String) async throws {
        _ = try await performWithoutResponse(path: "/filter-groups/\(id)", method: "DELETE")
    }

    func runtimeSettings() async throws -> RuntimeSettings {
        try await perform(path: "/settings")
    }

    func updateRuntimeSettings(_ payload: RuntimeSettingsUpdatePayload) async throws -> RuntimeSettings {
        try await perform(path: "/settings", method: "PATCH", body: try encoder.encode(payload))
    }
}
