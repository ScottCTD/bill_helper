# API Reference

Base URL: `http://localhost:8000/api/v1`

This file is the API index. Use it to find the focused API docs under `docs/api/`.

## Conventions

- JSON for most endpoints.
- `POST /agent/threads/{thread_id}/messages` and `POST /agent/threads/{thread_id}/messages/stream` use multipart form-data.
- Money values use integer minor units (`amount_minor`, `balance_minor`).
- Currency codes are normalized to uppercase server-side.
- Protected routes require `Authorization: Bearer <token>`.
- Non-admin principals are scoped to their own owned resources. Admin principals can read and mutate all user-owned resources and may create impersonation sessions through `/admin/users/{id}/login-as`.
- The web app uses password-backed bearer sessions only.

## API Doc Map

- `api/README.md`: topic map for route families.
- `api/core_ledger.md`: accounts, entries, groups, filter-groups, and dashboard endpoints.
- `api/catalogs_and_settings.md`: auth, admin, users, entities, tags, taxonomies, currencies, and runtime settings endpoints.
- `api/agent.md`: thread, message, run, tool-call, review, and attachment endpoints.

## Related Docs

- `docs/backend_index.md`
- `docs/data_model.md`
- `docs/features/entry_lifecycle.md`
- `docs/features/dashboard_analytics.md`
