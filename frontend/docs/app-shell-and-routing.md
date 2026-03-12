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
- `shadcn/ui`

## Build And Runtime

- dev server: `npm run dev`
- frontend tests: `npm run test`
- production build: `npm run build`
- API base override: `VITE_API_BASE_URL`

## App Shell

Defined in `frontend/src/App.tsx`.

Current shell behavior:

- `/login` is public
- every other route renders inside a protected shell that waits for auth resolution
- unauthenticated users are redirected to `/login`
- authenticated users see the shared sidebar plus route content
- impersonation sessions show a banner above protected content
- collapsible left sidebar (`Sidebar.tsx`) with navigation links for `Agent`, `Dashboard`, `Filters`, `Entries`, `Entities`, `Groups`, `Accounts`, `Properties`, and `Settings`
- admin users also get a dedicated `Admin` button in the expanded sidebar footer above the session card
- the session card in the sidebar footer shows only the current account name and a logout action
- route pages are lazy-loaded via `React.lazy` and `Suspense`
- the rich markdown editor bundle is loaded only when an editor dialog opens; development builds surface the exact runtime error above the textarea fallback, while production keeps the fallback generic
- desktop sidebar is resizable and persisted in `localStorage`
- on small screens the sidebar starts collapsed and can slide open

Route map:

- `/login` -> password sign-in page
- `/` -> agent home chat
- `/dashboard` -> dashboard analytics
- `/filters` -> saved filter-group workspace
- `/entries` -> entry list
- `/entries/:entryId` -> entry detail
- `/entities` -> entity list
- `/groups` -> groups workspace
- `/accounts` -> accounts workspace
- `/properties` -> tag/taxonomy/currency properties workspace
- `/settings` -> runtime settings + self-service password change
- `/admin` -> admin-only user/session management

Providers in `frontend/src/main.tsx`:

- `QueryClientProvider`
- `NotificationProvider`
- `AuthProvider`
- `BrowserRouter`
