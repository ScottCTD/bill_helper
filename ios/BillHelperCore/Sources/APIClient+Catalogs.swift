import Foundation

extension APIClient {
    func listEntities() async throws -> [Entity] {
        try await perform(path: "/entities")
    }

    func createEntity(_ payload: EntityCreatePayload) async throws -> Entity {
        try await perform(path: "/entities", method: "POST", body: try encoder.encode(payload))
    }

    func updateEntity(id: String, payload: EntityUpdatePayload) async throws -> Entity {
        try await perform(path: "/entities/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }

    func deleteEntity(id: String) async throws {
        _ = try await performWithoutResponse(path: "/entities/\(id)", method: "DELETE")
    }

    func listTags() async throws -> [Tag] {
        try await perform(path: "/tags")
    }

    func createTag(_ payload: TagCreatePayload) async throws -> Tag {
        try await perform(path: "/tags", method: "POST", body: try encoder.encode(payload))
    }

    func updateTag(id: Int, payload: TagUpdatePayload) async throws -> Tag {
        try await perform(path: "/tags/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }

    func deleteTag(id: Int) async throws {
        _ = try await performWithoutResponse(path: "/tags/\(id)", method: "DELETE")
    }

    func listCurrencies() async throws -> [Currency] {
        try await perform(path: "/currencies")
    }

    func listTaxonomies() async throws -> [Taxonomy] {
        try await perform(path: "/taxonomies")
    }

    func listTaxonomyTerms(taxonomyKey: String) async throws -> [TaxonomyTerm] {
        try await perform(path: "/taxonomies/\(taxonomyKey)/terms")
    }

    func createTaxonomyTerm(taxonomyKey: String, payload: TaxonomyTermCreatePayload) async throws -> TaxonomyTerm {
        try await perform(path: "/taxonomies/\(taxonomyKey)/terms", method: "POST", body: try encoder.encode(payload))
    }

    func updateTaxonomyTerm(
        taxonomyKey: String,
        termID: String,
        payload: TaxonomyTermUpdatePayload
    ) async throws -> TaxonomyTerm {
        try await perform(
            path: "/taxonomies/\(taxonomyKey)/terms/\(termID)",
            method: "PATCH",
            body: try encoder.encode(payload)
        )
    }

    func listUsers() async throws -> [User] {
        try await perform(path: "/users")
    }

    func createUser(_ payload: UserCreatePayload) async throws -> User {
        try await perform(path: "/users", method: "POST", body: try encoder.encode(payload))
    }

    func updateUser(id: String, payload: UserUpdatePayload) async throws -> User {
        try await perform(path: "/users/\(id)", method: "PATCH", body: try encoder.encode(payload))
    }
}
