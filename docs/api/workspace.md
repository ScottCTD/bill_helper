# Workspace API

Current routes:

- `GET /workspace`
- `POST /workspace/start`
- `POST /workspace/stop`
- `POST /workspace/ide/session`
- `GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS /workspace/ide/{path...}`
- `WS /workspace/ide/{path...}`

The snapshot and lifecycle routes are bearer-authenticated and always operate on the current principal's own workspace. The proxied IDE routes use a narrow HttpOnly workspace cookie issued by `POST /workspace/ide/session`; there is no query parameter or admin override for reading another user's sandbox from this surface.

## `GET /workspace`

Returns one snapshot object that describes lifecycle and IDE launch state:

- `workspace_enabled`: whether backend provisioning is enabled at all
- `starts_on_login`: whether authenticated app sessions best-effort auto-start the workspace
- `status`: current container state such as `disabled`, `created`, `running`, or `missing`
- `container_name` / `volume_name`: deterministic Docker resource names for the current user
- `ide_ready`: whether the proxied `code-server` endpoint is reachable right now
- `ide_launch_path`: same-origin launch path for the IDE proxy (`/api/v1/workspace/ide/` by default)
- `degraded_reason`: operator-facing reason when the IDE cannot be launched cleanly

Behavior notes:

- the backend enforces only the current `code-server` workspace contract; mismatched container definitions are recreated onto the current revision without preserving older mount-layout compatibility logic.
- if the configured image is missing, the snapshot returns `status="image_missing"` plus an operator-facing message instead of failing the whole page.
- login no longer blocks on Docker startup failures; the snapshot is the source of truth for degraded IDE state.

## `POST /workspace/start`

Starts the current user's provisioned workspace container and returns the same snapshot shape as `GET /workspace`.

Behavior notes:

- when provisioning is disabled, this is a no-op and the returned snapshot stays `disabled`
- the frontend auth bootstrap also calls this route best-effort after restoring an authenticated session so the IDE comes back after app reloads or backend restarts

## `POST /workspace/stop`

Stops the current user's workspace container and returns the same snapshot shape as `GET /workspace`.

Behavior notes:

- canonical files under `/data` remain untouched
- the named Docker volume stays intact, so `/workspace` contents persist across later restarts
- logout stops the container only after the user's last active app session is revoked

## `POST /workspace/ide/session`

Bearer-authenticated launch helper for the current principal.

Response shape:

- `launch_url`: relative same-origin IDE URL, typically `/api/v1/workspace/ide/?folder=/workspace`
- when the IDE opens `/workspace`, the writable volume root exposes `workspace/` for writable user files and `user_data/` as a symlink into the canonical read-only file tree (`/data/user_data/{uploads,artifacts}`), with friendly names derived from `display_name` / original filename while editor state is kept in a hidden internal directory
- the shipped workspace image also preinstalls the `chocolatedesue.modern-pdf-preview` extension and seeds minimal `code-server` user defaults so first launch skips the welcome page, keeps the opened folder trusted, and renders PDF entries in `user_data/` directly inside the IDE
- `snapshot`: the same workspace snapshot shape returned by `GET /workspace`

Behavior notes:

- ensures the user's workspace container is running
- waits for the `code-server` HTTP endpoint to become reachable
- the container startup expects the current volume layout only and does not migrate older `.code-server`, flat `/workspace`, or legacy `user_data` directory shapes
- sets a path-scoped `HttpOnly` workspace cookie for `/api/v1/workspace/ide/`
- reuses the current bearer session token inside that cookie rather than creating a second workspace-auth model

## `/workspace/ide/{path...}` proxy

Same-origin reverse proxy for the current user's `code-server` process.

Behavior notes:

- authenticates only from the narrow workspace cookie issued by `POST /workspace/ide/session`
- strips the `/workspace/ide` prefix before forwarding to the user's localhost-bound `code-server` port
- forwards both normal HTTP traffic and websocket upgrades
- `code-server` auth is disabled in the container because the backend session already gates access
- built-in `code-server` app/port proxying remains disabled in v1
