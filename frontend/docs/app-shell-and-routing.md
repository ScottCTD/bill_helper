# Frontend App Shell And Routing

## Stack

- React 19
- TypeScript
- Vite
- React Router
- TanStack Query
- Recharts
- React Flow
- Tailwind CSS
- `shadcn/ui` component primitives
- Radix UI primitives

## Build And Runtime

- Dev server: `npm run dev` (default `http://localhost:5173`)
- Frontend tests: `npm run test`
- Production build: `npm run build`
- API base override: `VITE_API_BASE_URL` (optional)
- Vite forces a fresh dep-optimization pass on each dev-server start so local restarts do not leave stale `.vite/deps` chunk references for the markdown editor

## App Shell And Routing

Defined in `frontend/src/App.tsx`.

Current shell behavior:

- startup session gate blocks route rendering until a local principal is selected or prefilled
- collapsible left sidebar (`Sidebar.tsx`) with navigation links for `Agent`, `Dashboard`, `Filters`, `Entries`, `Entities`, `Groups`, `Accounts`, `Properties`, and `Settings`
- sidebar behaves like a fixed tool rail: solid card background, stronger active-state marker, and a quieter footer that only exposes the active-principal switcher
- desktop sidebar is resizable and persists width in localStorage
- content canvas is route-driven and always renders inside the shared neutral workspace frame
- normal routes render within a centered content column over the shared muted canvas
- home route is still AI-first, but now renders the agent experience inside the same page header and content shell contract as the other workspaces
- route pages are lazy-loaded via `React.lazy` and `Suspense`
- the rich markdown editor bundle is loaded only when an editor dialog opens; development builds surface the exact runtime error above the textarea fallback, while production keeps the fallback generic
- on small screens the sidebar starts collapsed and can slide open

Route map:

- `/` -> AI home chat
- `/dashboard` -> dashboard analytics
- `/filters` -> first-class saved filter-group workspace
- `/entries` -> entry list, including optional `filter_group_id` URL filtering
- `/entities` -> entity list
- `/entries/:entryId` -> entry detail
- `/groups` -> derived group workspace
- `/accounts` -> accounts workspace
- `/properties` -> catalogs and taxonomy management
- `/settings` -> runtime settings workspace

Providers in `frontend/src/main.tsx`:

- `QueryClientProvider`
- `NotificationProvider`
- `PrincipalSessionProvider`
- `BrowserRouter`
