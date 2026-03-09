# API Reference

Base URL: `http://localhost:8000/api/v1`

This file is the API index. Use it to find the focused API docs under `docs/api/`.

## Conventions

- JSON for most endpoints.
- `POST /agent/threads/{thread_id}/messages` and `POST /agent/threads/{thread_id}/messages/stream` use multipart form-data.
- Money values use integer minor units (`amount_minor`, `balance_minor`).
- Currency codes are normalized to uppercase server-side.
- Protected routes require request principal header `X-Bill-Helper-Principal`; missing it returns `401`.
- The header is a development-session identity only; admin access comes from the persisted user role, not the header string by itself.
- Non-admin principals are scoped to their own user-owned resources (`accounts`, `entries`, `users`).
- Admin principal can access all user-owned resources and cross-user assignment flows.

## API Doc Map

- `api/README.md`: topic map for route families.
- `api/core-ledger.md`: accounts, entries, groups, and dashboard endpoints.
- `api/catalogs-and-settings.md`: users, entities, tags, taxonomies, currencies, and runtime settings endpoints.
- `api/agent.md`: thread, message, run, tool-call, review, and attachment endpoints.

## Related Docs

- `docs/backend.md`
- `docs/data-model.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
