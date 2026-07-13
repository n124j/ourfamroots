# OurFamRoots — Frontend Architecture v1.0

**Phase 7 | Stack: React 18 · TypeScript 5 · Vite 5 · Tailwind CSS 3 · Zustand 4 · React Query (TanStack Query) v5**

---

## 1. Guiding Principles

| Principle | Decision |
|---|---|
| Co-location | Tests, styles, and types live beside the feature they belong to |
| Feature isolation | Features import from `shared/`; never from sibling features |
| Server state ownership | React Query owns all server data; Zustand owns only UI / client-only state |
| Type safety | Strict TypeScript throughout; API types generated from OpenAPI spec |
| Performance-first | All pages lazy-loaded; tree canvas virtualised; images served via CDN with srcset |
| Responsive-first | Mobile breakpoint designed first; desktop is an enhancement |

---

## 2. Folder Structure

```
frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── .env.example
│
├── public/
│   └── fonts/
│
└── src/
    ├── main.tsx                  # App bootstrap, QueryClient, Router
    ├── App.tsx                   # Root component — router outlet only
    │
    ├── api/                      # HTTP layer (Axios instances + typed request fns)
    │   ├── client.ts             # Axios instance, interceptors, token refresh
    │   ├── auth.ts
    │   ├── persons.ts
    │   ├── trees.ts
    │   ├── events.ts
    │   ├── media.ts
    │   ├── search.ts
    │   └── reports.ts
    │
    ├── types/                    # Generated + hand-authored TypeScript types
    │   ├── api.gen.ts            # Auto-generated from OpenAPI (openapi-typescript)
    │   ├── domain.ts             # Domain aliases (Person, Tree, KinshipResult, …)
    │   └── common.ts             # ProblemDetail, PaginatedResponse, etc.
    │
    ├── router/
    │   ├── index.tsx             # createBrowserRouter — full route tree
    │   ├── guards/
    │   │   ├── AuthGuard.tsx     # Redirects unauthenticated users to /login
    │   │   └── GuestGuard.tsx    # Redirects authenticated users away from /login
    │   └── lazy.ts               # React.lazy() wrappers for every page
    │
    ├── store/                    # Zustand stores (client-only state)
    │   ├── auth.store.ts         # tokens, current user, tenant
    │   ├── ui.store.ts           # sidebar open/close, toasts, modals
    │   ├── canvas.store.ts       # tree canvas: viewport, selected nodes, zoom
    │   └── index.ts              # re-export
    │
    ├── queries/                  # React Query hooks (server state)
    │   ├── keys.ts               # Query key factory
    │   ├── auth.queries.ts
    │   ├── persons.queries.ts
    │   ├── trees.queries.ts
    │   ├── events.queries.ts
    │   ├── media.queries.ts
    │   ├── search.queries.ts
    │   └── reports.queries.ts
    │
    ├── shared/                   # Cross-feature reusable code
    │   ├── components/
    │   │   ├── primitives/       # Button, Input, Badge, Avatar, Spinner, …
    │   │   ├── compound/         # Modal, Dropdown, DatePicker, Toast, …
    │   │   ├── layout/           # AppShell, Sidebar, TopBar, PageHeader
    │   │   ├── UserAvatar.tsx    # Avatar with image or initial fallback; used in AppShell, Settings, Admin, Dashboard
    │   │   └── feedback/         # EmptyState, ErrorBoundary, SkeletonCard
    │   ├── hooks/
    │   │   ├── useDebounce.ts
    │   │   ├── useMediaQuery.ts
    │   │   ├── useScrollLock.ts
    │   │   └── useClickOutside.ts
    │   └── utils/
    │       ├── date.ts
    │       ├── name.ts           # formatDisplayName()
    │       └── cn.ts             # clsx + tailwind-merge helper
    │
    ├── features/                 # One directory per product feature
    │   ├── auth/
    │   │   ├── components/       # LoginForm, RegisterForm, ForgotPasswordForm
    │   │   └── hooks/            # useLogin, useRegister, useLogout
    │   │
    │   ├── dashboard/
    │   │   ├── components/       # RecentActivityFeed, StatCard, QuickActions
    │   │   └── hooks/
    │   │
    │   ├── tree/
    │   │   ├── canvas/           # D3/svg-based tree rendering engine
    │   │   │   ├── TreeCanvas.tsx
    │   │   │   ├── PersonNode.tsx
    │   │   │   ├── FamilyGroupNode.tsx
    │   │   │   ├── Edge.tsx
    │   │   │   └── useTreeLayout.ts  # Dagre/ELK layout algorithm hook
    │   │   ├── panels/           # AddPersonPanel, EditPersonPanel, RelationPanel
    │   │   ├── toolbar/          # ZoomControls, ExportButton, SearchBar
    │   │   └── hooks/
    │   │       ├── useTreeQuery.ts
    │   │       ├── useAddRelation.ts
    │   │       └── useKinship.ts
    │   │
    │   ├── profile/
    │   │   ├── components/       # PersonCard, TimelineEvent, MediaGallery
    │   │   └── hooks/
    │   │
    │   ├── search/
    │   │   ├── components/       # SearchBar, FilterPanel, ResultsList, ResultCard
    │   │   └── hooks/            # useSearchQuery, useSearchFilters
    │   │
    │   ├── reports/
    │   │   ├── components/       # ReportCard, GenerateReportModal, ReportPreview
    │   │   └── hooks/
    │   │
    │   └── settings/
    │       ├── components/       # ProfileForm, PasswordForm, NotificationPrefs, AvatarUpload
    │       └── hooks/
    │
    └── pages/                    # Thin page shells — compose features
        ├── auth/
        │   ├── LoginPage.tsx
        │   ├── RegisterPage.tsx
        │   └── ResetPasswordPage.tsx
        ├── DashboardPage.tsx
        ├── FamilyTreePage.tsx
        ├── ProfilePage.tsx
        ├── SearchPage.tsx
        ├── ReportsPage.tsx
        ├── SettingsPage.tsx
        └── NotFoundPage.tsx
```

---

## 3. Routing Architecture

### Route Tree (React Router v6)

```
/                           → redirect → /dashboard  [AuthGuard]
│
├── /login                  → LoginPage              [GuestGuard]
├── /register               → RegisterPage           [GuestGuard]
├── /reset-password         → ResetPasswordPage      [GuestGuard]
│
└── <AppShell>              → layout with sidebar + topbar [AuthGuard]
    ├── /dashboard          → DashboardPage
    ├── /trees/:treeId      → FamilyTreePage          (full-screen canvas)
    ├── /trees/:treeId/persons/:personId → ProfilePage
    ├── /search             → SearchPage
    ├── /reports            → ReportsPage
    └── /settings           → SettingsPage
        ├── /settings/profile         (avatar upload for local users, name, email)
        ├── /settings/security        (password change, danger zone)
        ├── /settings/appearance
        └── /settings/notifications
```

### Key Routing Decisions

**Lazy loading** — every page wrapped in `React.lazy()`. Vite code-splits at route level automatically. Suspense boundary at AppShell level with skeleton fallback.

**Auth guards** — `AuthGuard` reads from Zustand `auth.store`; if no access token it redirects to `/login?next=<current-path>`. On successful login, redirects back.

**Tree page** — `/trees/:treeId` is a standalone full-screen canvas route. It does not use the standard `AppShell` sidebar layout; it has its own minimal floating toolbar to maximise canvas space.

**URL state** — search filters, selected node, and zoom level are NOT stored in URL by default (held in Zustand). Deep-linkable share URLs (optional v2 feature) will serialise canvas.store to query params.

**Navigation guards** — unsaved changes in EditPersonPanel trigger a `useBlocker` prompt before navigation.

---

## 4. State Management Architecture

### Responsibility Split

| Layer | Technology | Owns |
|---|---|---|
| Server state | React Query | All data fetched from the API |
| Auth / session | Zustand `auth.store` | JWT tokens, current user, tenant |
| UI / shell | Zustand `ui.store` | Sidebar state, active modals, toast queue |
| Tree canvas | Zustand `canvas.store` | Viewport, zoom, selected node, pan position |
| Form state | React Hook Form | All form inputs (not global) |
| URL state | React Router | Route params, search params |

### 4.1 Zustand Stores

#### `auth.store.ts`
```
AuthState {
  accessToken: string | null
  user: CurrentUser | null
  tenant: Tenant | null
  isAuthenticated: boolean
  setTokens(access, refresh): void
  setUser(user, tenant): void
  logout(): void
}
```
Token is kept in memory (not localStorage) to prevent XSS. Refresh token stored in httpOnly cookie managed by the server.

#### `ui.store.ts`
```
UIState {
  sidebarOpen: boolean
  toasts: Toast[]
  activeModal: ModalId | null
  modalProps: Record<string, unknown>
  toggleSidebar(): void
  pushToast(toast): void
  dismissToast(id): void
  openModal(id, props?): void
  closeModal(): void
}
```

#### `canvas.store.ts`
```
CanvasState {
  treeId: string | null
  selectedPersonId: string | null
  zoom: number                    // 0.1 – 3.0
  pan: { x: number; y: number }
  focusPersonId: string | null    // center-of-tree anchor
  layoutDirection: 'TB' | 'LR'
  setSelected(id): void
  setZoom(z): void
  setPan(x, y): void
  focusOn(id): void
  reset(): void
}
```

### 4.2 React Query Conventions

#### Query Key Factory (`queries/keys.ts`)
```typescript
export const queryKeys = {
  trees: {
    all: ['trees'] as const,
    list: () => [...queryKeys.trees.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.trees.all, 'detail', id] as const,
  },
  persons: {
    all: (treeId: string) => ['persons', treeId] as const,
    detail: (treeId: string, id: string) => ['persons', treeId, 'detail', id] as const,
    ancestors: (treeId: string, id: string) => ['persons', treeId, id, 'ancestors'] as const,
    descendants: (treeId: string, id: string) => ['persons', treeId, id, 'descendants'] as const,
    kinship: (treeId: string, id1: string, id2: string) => ['persons', treeId, 'kinship', id1, id2] as const,
  },
  search: {
    results: (params: SearchParams) => ['search', params] as const,
  },
  reports: {
    all: ['reports'] as const,
    detail: (id: string) => ['reports', id] as const,
  },
}
```

#### Cache Strategy

| Query | staleTime | gcTime | Notes |
|---|---|---|---|
| Tree detail | 5 min | 30 min | Invalidated on any mutation to that tree |
| Person detail | 2 min | 15 min | Invalidated on edit/delete |
| Ancestors / descendants | 10 min | 60 min | Rarely changes; long cache |
| Search results | 30 sec | 5 min | User expects fresh results |
| Reports | 1 min | 10 min | |

#### Optimistic Updates

All relationship mutations (`addParent`, `addChild`, `addSpouse`, `addSibling`) use optimistic updates:
1. `onMutate` — snapshot current query cache, apply optimistic change
2. `onError` — roll back snapshot
3. `onSettled` — `invalidateQueries` for tree + ancestors/descendants

#### QueryClient Configuration (`main.tsx`)
```
defaultOptions: {
  queries: {
    staleTime: 60_000,
    retry: (count, error) => count < 2 && error.status !== 401 && error.status !== 404,
    refetchOnWindowFocus: false,   // off for canvas — avoid layout re-renders
  },
  mutations: {
    onError: (error) => ui.store.pushToast({ kind: 'error', message: error.detail }),
  }
}
```

---

## 5. Component Architecture

### Layer Pyramid

```
┌─────────────────────────────────────┐
│            Pages                    │  Thin shells; assemble feature blocks
├─────────────────────────────────────┤
│         Feature Components          │  Domain-aware; own queries/mutations
├─────────────────────────────────────┤
│         Compound Components         │  Multi-element, stateful UI patterns
├─────────────────────────────────────┤
│         Primitive Components        │  Single-element, fully headless/unstyled
└─────────────────────────────────────┘
```

### 5.1 Primitive Components (`shared/components/primitives/`)

Stateless, no data fetching, fully typed props, polymorphic where needed.

| Component | Description |
|---|---|
| `Button` | variant (primary/secondary/ghost/danger), size (sm/md/lg), loading state |
| `Input` | controlled, error state, prefix/suffix slot |
| `Textarea` | auto-resize, character count |
| `Select` | accessible, searchable via Combobox pattern |
| `Checkbox` / `Radio` | controlled, indeterminate support |
| `Badge` | colour-coded status indicators |
| `Avatar` | image + initials fallback, size variants |
| `Spinner` | size + colour variants |
| `Tooltip` | Floating UI-powered, keyboard accessible |
| `IconButton` | Button + icon, aria-label required |

### 5.2 Compound Components (`shared/components/compound/`)

Stateful UI patterns; may use Radix UI headless primitives internally.

| Component | Description |
|---|---|
| `Modal` | Radix Dialog, focus trap, animated enter/exit |
| `Dropdown` | Radix DropdownMenu, keyboard navigable |
| `DatePicker` | react-day-picker integration, keyboard navigable |
| `Toast` | Stacked, auto-dismiss, action CTA slot |
| `Tabs` | Radix Tabs, URL-sync optional |
| `Breadcrumb` | Path from router context |
| `Pagination` | Cursor + page-number variants |
| `FileUpload` | Drag-and-drop zone, progress indicator |
| `ConfirmDialog` | Wraps Modal; used for destructive actions |

### 5.3 Layout Components (`shared/components/layout/`)

| Component | Description |
|---|---|
| `AppShell` | Sidebar + TopBar + main `<Outlet>` |
| `Sidebar` | Collapsible nav, mobile drawer, keyboard accessible |
| `TopBar` | Breadcrumb, global search trigger, user avatar menu |
| `PageHeader` | Title, subtitle, action slot (used within pages) |
| `Section` | Titled content block with optional divider |

### 5.4 Feature Components (`features/*/components/`)

Domain-aware; fetch their own data via React Query hooks.

| Feature | Key Components |
|---|---|
| `dashboard` | `ActivityFeed`, `StatCard`, `QuickAddButton`, `RecentTreesGrid` |
| `tree` | `TreeCanvas`, `PersonNodeCard`, `EdgeLine`, `AddRelationPanel`, `EditPersonPanel`, `ZoomControls`, `MiniMap` |
| `profile` | `PersonHero`, `LifeTimeline`, `RelativesPanel`, `MediaGallery`, `KinshipBadge` |
| `search` | `GlobalSearchBar`, `FilterSidebar`, `ResultsList`, `PersonResultCard` |
| `reports` | `ReportTypeCard`, `GenerateReportModal`, `ReportHistoryTable` |
| `settings` | `ProfileForm`, `ChangePasswordForm`, `NotificationPrefsForm`, `DangerZone` |

### 5.5 Naming Conventions

- Files: `PascalCase.tsx` for components, `camelCase.ts` for hooks/utils
- Hooks: always prefix `use` (`usePersonQuery`, `useAddParent`)
- All components export a named export AND a `default` export
- Props interface named `<ComponentName>Props`
- Event handlers named `on<Event>` on the interface, `handle<Event>` inside the component

---

## 6. Page Designs

### 6.1 Dashboard (`/dashboard`)

**Purpose:** Entry point after login — at-a-glance status and quick actions.

**Layout:** 3-column grid on desktop, single column on mobile.

**Sections:**
- **Hero bar** — greeting, last-login timestamp, quick-add CTA
- **My Trees** — card grid showing each family tree (name, member count, last modified). Max 6 visible; "View all" link.
- **Recent Activity** — chronological feed of tree mutations (person added, event recorded, media uploaded). Paginated, real-time via polling (30s).
- **Stat Strip** — total persons, total media, trees shared with me
- **Suggested Actions** — contextual prompts ("You have 3 persons with no birth date")

**Responsive:**
- Mobile: stacked single column; hero bar condensed
- Tablet: 2-column grid for trees, activity below
- Desktop: 3-column; trees + stats left, activity centre-right

---

### 6.2 Family Tree (`/trees/:treeId`)

**Purpose:** Interactive visual graph of the family tree.

**Layout:** Full-screen canvas; floating UI panels.

**Canvas:**
- SVG-based directed graph rendered with D3
- Layout algorithm: Dagre (top-to-bottom generational layout)
- Node: `PersonNodeCard` — avatar, name, birth/death years, sex colour-coded border
- Edge: straight or curved connector lines, labelled with relationship type
- Navigation: pan (drag), zoom (scroll wheel / pinch), keyboard arrow keys

**Floating UI:**
- **Toolbar** (top): tree title, zoom controls, layout toggle (TB/LR), export, search-in-tree
- **MiniMap** (bottom-right): viewport indicator over full graph
- **Selection Panel** (right drawer, 380px): opens on node click — person summary, relationship actions (Add Parent / Child / Spouse / Sibling), "Open Profile" link
- **Add Relation Wizard** (modal): step-by-step flow — select relation type → search/create person → confirm

**Responsive:**
- Mobile: canvas fills viewport; toolbar collapses to hamburger; panel becomes bottom sheet

---

### 6.3 Profile (`/trees/:treeId/persons/:personId`)

**Purpose:** Deep-dive view of a single person.

**Layout:** Two-column on desktop (main content + relatives sidebar), single column on mobile.

**Sections:**
- **Hero** — large avatar/photo, name (given + surname), life dates, sex, kinship label relative to the current user's anchor
- **Vital Events** — birth, death, baptism, burial as a timeline
- **Life Events** — all events in chronological order (residence, occupation, education, immigration, …)
- **Media Gallery** — photo grid; click to lightbox
- **Family Relationships** — grouped: parents, siblings, spouses, children; each as a mini PersonCard that links to their own profile
- **Notes** — free-text notes with timestamps
- **Edit Button** — opens EditPersonPanel slide-over

**Responsive:**
- Mobile: relatives sidebar moves below main content

---

### 6.4 Search (`/search`)

**Purpose:** Find persons, events, or media across all trees the user has access to.

**Layout:** Filter sidebar (collapsible) + results main area.

**Features:**
- Full-text search with 300ms debounce
- Filter panel: tree, sex, birth year range, death year range, living/deceased
- Results list: `PersonResultCard` (name, tree, birth/death, match snippet)
- Sort: relevance (default), name A–Z, birth year
- Keyboard shortcut: `Cmd/Ctrl+K` opens global search from anywhere

**Responsive:**
- Mobile: filter panel hidden behind "Filters" button, opens as bottom sheet

---

### 6.5 Reports (`/reports`)

**Purpose:** Generate and download genealogy reports.

**Layout:** Two sections — Generate new report + History table.

**Report Types (v1):**
| Type | Format | Description |
|---|---|---|
| Pedigree Chart | PDF | Ancestors of a focus person, N generations |
| Descendant Report | PDF | All descendants, narrative style |
| Family Group Sheet | PDF | One family unit (parents + children) |
| Person Summary | PDF | Single person's full profile |
| GEDCOM Export | .ged | Full tree in standard genealogy format |

**Flow:**
1. Click a report type card
2. `GenerateReportModal`: select focus person + parameters (e.g., number of generations)
3. POST to API → report queued → polling until complete → download link

**History table:** report name, created date, status, download/delete actions.

**Responsive:** Single column on mobile; table becomes card list.

---

### 6.6 Settings (`/settings`)

**Purpose:** Manage account and preferences.

**Layout:** Left tab nav + form area (desktop); stacked accordion (mobile).

**Sub-pages:**

| Tab | Contents |
|---|---|
| **Profile** | Given name, surname, display name, email, profile photo upload |
| **Account** | Change password, delete account (danger zone) |
| **Notifications** | Email notification toggles (new share, activity digest) |

All forms use React Hook Form + Zod validation. Inline field errors. Save button enables only when dirty.

---

## 7. Responsive Design Strategy

### Breakpoints (Tailwind default)

| Token | Width | Target |
|---|---|---|
| `sm` | 640px | Large phones (landscape) |
| `md` | 768px | Tablets |
| `lg` | 1024px | Small laptops |
| `xl` | 1280px | Desktop |
| `2xl` | 1536px | Large desktop |

### Core Patterns

**Mobile-first authoring** — all Tailwind classes written for mobile, then overridden at larger breakpoints. No `max-*` breakpoints except for rare overrides.

**Sidebar** — fixed on `lg+`, hidden off-canvas (slide-in drawer) on `sm/md`. Controlled by `ui.store.sidebarOpen`.

**Navigation** — top navigation bar on mobile; left sidebar on desktop.

**Panels and drawers** — right-side panels (EditPersonPanel) render as full-screen modals on mobile, 380px side drawers on desktop.

**Table → Card fallback** — data tables (reports history, search results) switch to card lists below `md` breakpoint.

**Touch targets** — all interactive elements minimum 44×44px on mobile (Tailwind `min-h-[44px] min-w-[44px]`).

**Tree Canvas** — panning on mobile via touch events. Pinch-to-zoom. Double-tap to open person panel.

### Typography Scale

| Style | Mobile | Desktop |
|---|---|---|
| Display | `text-2xl font-bold` | `text-4xl font-bold` |
| Heading 1 | `text-xl font-semibold` | `text-2xl font-semibold` |
| Heading 2 | `text-lg font-semibold` | `text-xl font-semibold` |
| Body | `text-sm` | `text-base` |
| Caption | `text-xs` | `text-sm` |

---

## 8. Design Tokens (Tailwind Configuration)

```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f9ff',
          500: '#0ea5e9',   // primary interactive
          700: '#0369a1',   // primary hover
          900: '#0c4a6e',
        },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f8fafc',
          elevated: '#f1f5f9',
        },
        border: {
          DEFAULT: '#e2e8f0',
          strong: '#cbd5e1',
        },
        // Sex-coded node borders (tree canvas)
        male:    '#3b82f6',
        female:  '#ec4899',
        unknown: '#94a3b8',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        card: '12px',
        node: '8px',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.05)',
        elevated: '0 4px 6px -1px rgb(0 0 0 / 0.08)',
        canvas: '0 10px 25px -5px rgb(0 0 0 / 0.12)',
      },
    },
  },
}
```

---

## 9. API Layer (`src/api/`)

### Axios Client (`client.ts`)

- Base URL from `VITE_API_BASE_URL` env variable
- Request interceptor: attaches `Authorization: Bearer <token>` from `auth.store`
- Response interceptor: on 401 → attempts silent refresh via `/auth/refresh` → retries original request once → on second 401 logs out and redirects to `/login`
- All requests include `X-Tenant-ID` header from `auth.store.tenant.id`
- Type-safe request functions return `Promise<T>` (no raw `AxiosResponse` leakage)

### Type Generation

OpenAPI spec (`OurFamRoots_APIDesign_v1.0`) fed into `openapi-typescript` to generate `src/types/api.gen.ts` at build time. CI fails if generated types differ from checked-in file.

```
npm run gen:types   # openapi-typescript ./openapi.yaml -o src/types/api.gen.ts
```

---

## 10. Tooling & DX

| Tool | Purpose |
|---|---|
| **Vite 5** | Dev server, HMR, build |
| **TypeScript 5** | Strict mode, path aliases (`@/` → `src/`) |
| **ESLint** | `@typescript-eslint`, `eslint-plugin-react-query` |
| **Prettier** | Consistent formatting |
| **Vitest** | Unit tests for hooks/utils |
| **Playwright** | E2E tests (Phase 9) |
| **openapi-typescript** | API type generation from spec |
| **tailwind-merge + clsx** | Safe className merging (`cn()` utility) |

### Path Aliases (`vite.config.ts`)
```
@/          → src/
@features/  → src/features/
@shared/    → src/shared/
@queries/   → src/queries/
@store/     → src/store/
@api/       → src/api/
@types/     → src/types/
```

---

## 11. Environment Variables

```bash
# .env.example
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=OurFamRoots
VITE_ENABLE_DEVTOOLS=true          # React Query Devtools
VITE_SENTRY_DSN=                   # optional — error monitoring
```

---

## 12. Phase 8 Preview

Phase 8 will implement component code for the design system (primitives + compound), the AppShell layout, and the tree canvas engine.
