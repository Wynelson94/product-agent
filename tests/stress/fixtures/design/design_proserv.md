---
stack_id: nextjs-prisma
product_type: multi_tenant
status: ready
---

# DESIGN.md — Professional Services SaaS

Multi-tenant SaaS for professional services teams: project management, time tracking, invoicing, and client billing. Stack: Next.js 16 App Router + Prisma + Neon Postgres + Clerk + Stripe + Vercel Blob.

---

## §1 — Data Model (Prisma Schema)

```prisma
// prisma/schema.prisma

generator client {
  provider        = "prisma-client-js"
  previewFeatures = ["driverAdapters"]
}

datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  directUrl = env("DIRECT_URL")
}

// ─── Enums ────────────────────────────────────────────────────────────────────

enum Role {
  OWNER
  ADMIN
  MEMBER
  VIEWER
}

enum PlanTier {
  STARTER    // up to 3 active projects, 3 members, 30-day audit log
  PRO        // up to 20 active projects, 15 members, 90-day audit log
  ENTERPRISE // unlimited, 1-year audit log
}

enum InvoiceStatus {
  DRAFT
  SENT
  PAID
  OVERDUE
  VOID
}

enum ResourceType {
  ORGANIZATION
  PROJECT
  CLIENT
  TIME_ENTRY
  INVOICE
  MEMBERSHIP
  SUBSCRIPTION
}

// ─── Core Tables ──────────────────────────────────────────────────────────────

model User {
  id        String   @id @default(cuid())
  clerkId   String   @unique  // Clerk user ID — mapped on first sign-in
  email     String   @unique
  name      String
  avatarUrl String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  memberships  Membership[]
  timeEntries  TimeEntry[]
  auditLogs    AuditLog[]

  @@map("users")
}

model Organization {
  id         String   @id @default(cuid())
  clerkOrgId String   @unique  // Clerk org ID — mapped on org.created webhook
  name       String
  slug       String   @unique
  logoUrl    String?
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  // Stripe billing fields
  stripeCustomerId     String?   @unique
  stripeSubscriptionId String?   @unique
  stripePriceId        String?
  planTier             PlanTier  @default(STARTER)
  planSeats            Int       @default(3)
  currentPeriodEnd     DateTime?
  cancelAtPeriodEnd    Boolean   @default(false)

  memberships Membership[]
  clients     Client[]
  projects    Project[]
  invoices    Invoice[]
  auditLogs   AuditLog[]

  @@map("organizations")
}

model Membership {
  id        String   @id @default(cuid())
  orgId     String
  userId    String
  role      Role     @default(VIEWER)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  organization Organization @relation(fields: [orgId], references: [id], onDelete: Cascade)
  user         User         @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([orgId, userId])
  @@index([orgId])
  @@index([userId])
  @@map("memberships")
}

// ─── Client & Project ─────────────────────────────────────────────────────────

model Client {
  id        String   @id @default(cuid())
  orgId     String
  name      String
  email     String?
  phone     String?
  address   String?
  notes     String?
  archived  Boolean  @default(false)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  organization Organization @relation(fields: [orgId], references: [id], onDelete: Cascade)
  projects     Project[]
  invoices     Invoice[]

  @@index([orgId])
  @@index([orgId, archived])
  @@map("clients")
}

model Project {
  id          String   @id @default(cuid())
  orgId       String
  clientId    String?
  name        String
  description String?
  color       String   @default("#6366f1")  // UI color tag
  hourlyRate  Decimal? @db.Decimal(10, 2)   // default billing rate
  budget      Decimal? @db.Decimal(10, 2)   // total budget cap
  active      Boolean  @default(true)
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  organization Organization @relation(fields: [orgId], references: [id], onDelete: Cascade)
  client       Client?      @relation(fields: [clientId], references: [id], onDelete: SetNull)
  timeEntries  TimeEntry[]

  @@index([orgId])
  @@index([orgId, active])
  @@index([orgId, clientId])
  @@map("projects")
}

// ─── Time Tracking ────────────────────────────────────────────────────────────

model TimeEntry {
  id              String    @id @default(cuid())
  orgId           String
  userId          String
  projectId       String
  description     String?
  startedAt       DateTime
  stoppedAt       DateTime?  // NULL = active timer
  durationMinutes Int?       // manual override; computed from start/stop if null
  billable        Boolean    @default(true)
  hourlyRate      Decimal?   @db.Decimal(10, 2)  // rate snapshot at creation
  createdAt       DateTime   @default(now())
  updatedAt       DateTime   @updatedAt

  organization     Organization      @relation(fields: [orgId], references: [id], onDelete: Cascade)
  user             User              @relation(fields: [userId], references: [id], onDelete: Cascade)
  project          Project           @relation(fields: [projectId], references: [id], onDelete: Cascade)
  invoiceLineItems InvoiceLineItem[]

  @@index([orgId])
  @@index([orgId, userId])
  @@index([orgId, projectId])
  @@index([orgId, startedAt(sort: Desc)])
  // Partial unique index enforced via raw SQL migration (below): one active timer per user per org
  @@map("time_entries")
}

// ─── Invoicing ────────────────────────────────────────────────────────────────

model Invoice {
  id          String        @id @default(cuid())
  orgId       String
  clientId    String
  number      String        // formatted: INV-2026-0042
  status      InvoiceStatus @default(DRAFT)
  issuedAt    DateTime      @default(now())
  dueDate     DateTime
  notes       String?
  pdfUrl      String?       // Vercel Blob URL — set after PDF generation
  totalAmount Decimal       @db.Decimal(10, 2) @default(0)
  currency    String        @default("USD")
  createdAt   DateTime      @default(now())
  updatedAt   DateTime      @updatedAt

  organization Organization    @relation(fields: [orgId], references: [id], onDelete: Cascade)
  client       Client          @relation(fields: [clientId], references: [id], onDelete: Restrict)
  lineItems    InvoiceLineItem[]

  @@unique([orgId, number])
  @@index([orgId])
  @@index([orgId, status])
  @@index([orgId, clientId])
  @@index([orgId, dueDate])
  @@map("invoices")
}

model InvoiceLineItem {
  id          String   @id @default(cuid())
  invoiceId   String
  timeEntryId String?  // NULL = manual line item
  description String
  quantity    Decimal  @db.Decimal(10, 3)  // hours or units
  unitPrice   Decimal  @db.Decimal(10, 2)
  amount      Decimal  @db.Decimal(10, 2)  // computed: quantity × unitPrice
  createdAt   DateTime @default(now())

  invoice   Invoice    @relation(fields: [invoiceId], references: [id], onDelete: Cascade)
  timeEntry TimeEntry? @relation(fields: [timeEntryId], references: [id], onDelete: SetNull)

  @@index([invoiceId])
  @@map("invoice_line_items")
}

// ─── Audit Log ────────────────────────────────────────────────────────────────

model AuditLog {
  id           String       @id @default(cuid())
  orgId        String
  actorId      String       // User.id
  actorRole    Role
  action       String       // e.g. "project.created", "invoice.sent", "member.removed"
  resourceType ResourceType
  resourceId   String
  metadata     Json         @default("{}")  // before/after diffs, extra context
  ipAddress    String?
  createdAt    DateTime     @default(now())

  organization Organization @relation(fields: [orgId], references: [id], onDelete: Cascade)
  actor        User         @relation(fields: [actorId], references: [id], onDelete: Cascade)

  @@index([orgId, createdAt(sort: Desc)])
  @@index([orgId, actorId])
  @@index([orgId, resourceType, resourceId])
  @@map("audit_logs")
}

// ─── Invoice Sequence Counter ─────────────────────────────────────────────────
// Separate table for SELECT FOR UPDATE to prevent race conditions in sequential numbering.

model InvoiceSequence {
  orgId   String @id
  lastSeq Int    @default(0)

  @@map("invoice_sequences")
}
```

### Additional Database Migrations (Raw SQL)

```sql
-- migrations/YYYYMMDD_partial_unique_timer/migration.sql

-- One active timer per user per org (stoppedAt IS NULL = running).
-- Prisma does not support partial unique indexes in the schema file —
-- must be applied as a raw migration.
CREATE UNIQUE INDEX time_entries_one_active_per_user
  ON time_entries (org_id, user_id)
  WHERE stopped_at IS NULL;

-- Enable RLS on all tenant tables (defense-in-depth safety net behind app-layer org scoping)
ALTER TABLE organizations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships        ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients            ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects           ENABLE ROW LEVEL SECURITY;
ALTER TABLE time_entries       ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices           ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs         ENABLE ROW LEVEL SECURITY;

-- SECURITY DEFINER helper reads the tenant context set by tenantPrisma().
-- SECURITY DEFINER is required so the function executes with elevated privileges
-- and does NOT trigger RLS on memberships when resolving the org — avoiding
-- circular self-referential policy evaluation.
CREATE OR REPLACE FUNCTION current_org_id()
RETURNS text AS $$
  SELECT current_setting('app.current_org_id', true)
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- RLS Policies

-- organizations: only the current org's row is visible
CREATE POLICY "org_isolation" ON organizations
  FOR ALL USING (id = current_org_id());

-- memberships: scoped to org
CREATE POLICY "membership_isolation" ON memberships
  FOR ALL USING (org_id = current_org_id());

-- clients
CREATE POLICY "client_isolation" ON clients
  FOR ALL USING  (org_id = current_org_id())
  WITH CHECK     (org_id = current_org_id());

-- projects
CREATE POLICY "project_isolation" ON projects
  FOR ALL USING  (org_id = current_org_id())
  WITH CHECK     (org_id = current_org_id());

-- time_entries
CREATE POLICY "time_entry_isolation" ON time_entries
  FOR ALL USING  (org_id = current_org_id())
  WITH CHECK     (org_id = current_org_id());

-- invoices
CREATE POLICY "invoice_isolation" ON invoices
  FOR ALL USING  (org_id = current_org_id())
  WITH CHECK     (org_id = current_org_id());

-- invoice_line_items: org check via parent invoice.
-- Safe to subquery RLS-enabled `invoices` here because current_org_id() is
-- SECURITY DEFINER and reads only a session variable — it does NOT query
-- invoice_line_items, so there is no circular dependency.
CREATE POLICY "line_item_isolation" ON invoice_line_items
  FOR ALL USING (
    invoice_id IN (
      SELECT id FROM invoices WHERE org_id = current_org_id()
    )
  )
  WITH CHECK (
    invoice_id IN (
      SELECT id FROM invoices WHERE org_id = current_org_id()
    )
  );

-- audit_logs
CREATE POLICY "audit_log_isolation" ON audit_logs
  FOR ALL USING  (org_id = current_org_id())
  WITH CHECK     (org_id = current_org_id());
```

---

## §2 — Pages / Routes

| Route | Purpose | Auth Required | Min Role |
|-------|---------|---------------|----------|
| `/` | Marketing landing page | No | — |
| `/sign-in/[[...sign-in]]` | Clerk sign-in | No | — |
| `/sign-up/[[...sign-up]]` | Clerk sign-up | No | — |
| `/onboarding` | Create or join an org after first sign-in | Yes | any authenticated |
| `/dashboard` | KPI summary: billable hours, open invoices, active projects | Yes | VIEWER |
| `/projects` | Paginated project list with filters | Yes | VIEWER |
| `/projects/new` | Create project form | Yes | ADMIN |
| `/projects/[id]` | Project detail: time log, budget progress, team | Yes | VIEWER |
| `/projects/[id]/edit` | Edit project name, rate, client, budget | Yes | ADMIN |
| `/clients` | Client list with search | Yes | VIEWER |
| `/clients/new` | Create client form | Yes | ADMIN |
| `/clients/[id]` | Client detail: projects, invoice history | Yes | VIEWER |
| `/clients/[id]/edit` | Edit client details | Yes | ADMIN |
| `/time` | Time-entry list for the caller; admins see team view | Yes | MEMBER |
| `/time/new` | Start or log a manual time entry | Yes | MEMBER |
| `/time/[id]/edit` | Edit own entry (MEMBER); any entry (ADMIN+) | Yes | MEMBER |
| `/invoices` | Invoice list with status filters | Yes | **ADMIN** |
| `/invoices/new` | Create invoice wizard | Yes | ADMIN |
| `/invoices/[id]` | Invoice detail with PDF preview and status actions | Yes | **ADMIN** |
| `/invoices/[id]/edit` | Edit DRAFT invoice line items | Yes | ADMIN |
| `/settings` | **Role-aware redirect** — see note below | Yes | ADMIN |
| `/settings/general` | Org name, logo, slug, danger zone | Yes | OWNER |
| `/settings/members` | Invite, change roles, remove members | Yes | ADMIN |
| `/settings/billing` | Plan tier, seat count, Stripe portal link | Yes | OWNER |
| `/settings/audit` | Paginated audit log with filters | Yes | ADMIN |

> **`/settings` role-aware redirect** (fixes Issue #1): `(app)/settings/page.tsx` reads the caller's role from Clerk session claims. If `role === 'OWNER'`, calls `redirect('/settings/general')`. Otherwise — ADMIN is the minimum role enforced by `proxy.ts`, so any caller reaching this page is at least ADMIN — calls `redirect('/settings/members')`. This prevents the dead-end where an ADMIN is bounced into the OWNER-only `/settings/general` page.

> **`/invoices` and `/invoices/[id]` min role = ADMIN** (fixes Issue #3): MEMBERs are time-entry workers with no financial visibility. Setting the minimum to ADMIN is internally consistent with the capability matrix (`view:invoice: ['OWNER', 'ADMIN']`). MEMBERs are blocked at the route guard in `proxy.ts` before reaching any invoice page.

---

## §3 — Components

### Layout
| Component | File | Description |
|-----------|------|-------------|
| `AppShell` | `components/layout/app-shell.tsx` | Root shell: sidebar + top bar + main content area |
| `Sidebar` | `components/layout/sidebar.tsx` | Nav links filtered by role; active org switcher |
| `TopBar` | `components/layout/top-bar.tsx` | Breadcrumb, notifications bell, user avatar menu |
| `OrgSwitcher` | `components/layout/org-switcher.tsx` | Clerk `<OrganizationSwitcher>` wrapper |
| `PlanBanner` | `components/layout/plan-banner.tsx` | Upgrade prompt shown when approaching plan limits |

### Feature — Projects
| Component | File | Description |
|-----------|------|-------------|
| `ProjectCard` | `components/projects/project-card.tsx` | Card with name, client, budget progress bar, active/archived badge |
| `ProjectList` | `components/projects/project-list.tsx` | Grid of `ProjectCard` with filter + sort controls |
| `ProjectForm` | `components/projects/project-form.tsx` | Create/edit form: name, client select, hourly rate, budget, color picker |
| `ProjectBudgetBar` | `components/projects/project-budget-bar.tsx` | Animated progress bar: spent vs. budget |

### Feature — Time Tracking
| Component | File | Description |
|-----------|------|-------------|
| `TimerWidget` | `components/time/timer-widget.tsx` | Sticky active-timer bar: project, elapsed HH:MM:SS, stop button |
| `TimeEntryRow` | `components/time/time-entry-row.tsx` | Table row: date, project, description, duration, billable toggle, actions |
| `TimeEntryTable` | `components/time/time-entry-table.tsx` | Paginated table of `TimeEntryRow` with week/month grouping |
| `TimeEntryForm` | `components/time/time-entry-form.tsx` | Start timer or log manual entry: project select, description, date/time pickers |
| `DailyTotalBar` | `components/time/daily-total-bar.tsx` | Per-day billable total chip in the weekly view |

### Feature — Clients
| Component | File | Description |
|-----------|------|-------------|
| `ClientCard` | `components/clients/client-card.tsx` | Card with name, email, active project count, revenue badge |
| `ClientForm` | `components/clients/client-form.tsx` | Create/edit: name, email, phone, address, notes |

### Feature — Invoices
| Component | File | Description |
|-----------|------|-------------|
| `InvoiceStatusBadge` | `components/invoices/invoice-status-badge.tsx` | Color-coded badge for DRAFT/SENT/PAID/OVERDUE/VOID |
| `InvoiceList` | `components/invoices/invoice-list.tsx` | Table with status filter tabs, sort by date/amount |
| `InvoiceForm` | `components/invoices/invoice-form.tsx` | Wizard: select client → import billable time → add manual line items |
| `LineItemEditor` | `components/invoices/line-item-editor.tsx` | Drag-reorderable rows: description, qty, unit price, computed amount |
| `InvoicePreview` | `components/invoices/invoice-preview.tsx` | Read-only PDF-style preview rendered with `@react-pdf/renderer` |
| `InvoiceActions` | `components/invoices/invoice-actions.tsx` | Context-aware buttons: Send, Mark Paid, Void, Download PDF |

### Feature — Settings
| Component | File | Description |
|-----------|------|-------------|
| `MemberTable` | `components/settings/member-table.tsx` | List members with role dropdown + remove button |
| `InviteForm` | `components/settings/invite-form.tsx` | Email invite with role selector |
| `BillingCard` | `components/settings/billing-card.tsx` | Plan name, seat count, renewal date, Stripe portal button |
| `AuditLogTable` | `components/settings/audit-log-table.tsx` | Paginated log: actor avatar, action, resource, timestamp, IP |
| `AuditLogFilters` | `components/settings/audit-log-filters.tsx` | Filter by actor, action type, resource type, date range |
| `DangerZone` | `components/settings/danger-zone.tsx` | Delete org with `ConfirmDialog` — OWNER only |

### Shared / UI
| Component | File | Description |
|-----------|------|-------------|
| `PageHeader` | `components/ui/page-header.tsx` | H1 + optional subtitle + right-side action slot |
| `EmptyState` | `components/ui/empty-state.tsx` | Icon + heading + description + optional CTA button |
| `DataTable` | `components/ui/data-table.tsx` | shadcn `Table` + TanStack sorting/pagination wrapper |
| `ConfirmDialog` | `components/ui/confirm-dialog.tsx` | shadcn `AlertDialog` for destructive confirmations |
| `StatusSelect` | `components/ui/status-select.tsx` | Controlled select for enum transitions |
| `CurrencyInput` | `components/ui/currency-input.tsx` | Formatted decimal input with locale-aware display |
| `DurationInput` | `components/ui/duration-input.tsx` | HH:MM input that serialises to minutes |
| `DateRangePicker` | `components/ui/date-range-picker.tsx` | shadcn Calendar-based range picker |
| `RoleBadge` | `components/ui/role-badge.tsx` | Color-coded OWNER/ADMIN/MEMBER/VIEWER pill |
| `PlanGate` | `components/ui/plan-gate.tsx` | Wraps children; renders upgrade prompt when plan insufficient |
| `RoleGate` | `components/ui/role-gate.tsx` | Wraps children; renders null or fallback when role insufficient |

---

## §4 — Auth Flow

### Sign-Up
1. User visits `/sign-up` → Clerk `<SignUp>` component handles email/social.
2. Clerk fires `user.created` webhook → `POST /api/webhooks/clerk` → upsert `User` row.
3. `proxy.ts` detects session has no `orgId` → `redirect('/onboarding')`.
4. `/onboarding`: user creates a new org (`<CreateOrganization>`) or accepts an invite. Clerk fires `organization.created` webhook → upsert `Organization`, create OWNER `Membership`.
5. Clerk sets `orgId` in session claims. `proxy.ts` allows access → `redirect('/dashboard')`.

### Sign-In
1. User visits `/sign-in` → Clerk `<SignIn>`.
2. Clerk issues JWT with custom session claims `{ userId, orgId, role }` (populated from `Membership` via Clerk session customization template).
3. `proxy.ts` validates JWT on every request. Injects `x-user-id`, `x-org-id`, `x-user-role` headers for Server Components.
4. If `orgId` absent → `redirect('/onboarding')`.

### Session Management
- JWT in `HttpOnly` cookie managed entirely by Clerk.
- `organizationMembership.updated` Clerk webhook re-syncs `Membership.role` in DB and calls `updateUserMetadata` to refresh session claims.
- Runtime Cache stores `{ orgId, role }` per user with 30-second TTL to avoid DB round-trips on every render.

### Protected Route Handling (`proxy.ts`)
```
/sign-in, /sign-up, /api/webhooks/* → public
/api/cron/*                          → verify CRON_SECRET header only
All other routes → clerkMiddleware():
  No session               → redirect /sign-in
  Session, no orgId        → redirect /onboarding
  Session + orgId          → resolve role from Clerk session claims
  Inject x-user-id, x-org-id, x-user-role headers
  Route RBAC gates:
    /settings/general, /settings/billing         → require OWNER
    /invoices, /invoices/*                        → require ADMIN
    /settings, /settings/members, /settings/audit → require ADMIN
    /clients/new, /projects/new, /*/edit          → require ADMIN
    /time, /time/*                                → require MEMBER
    /dashboard, /projects, /clients               → require VIEWER
```

---

## §5 — API Routes

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| `POST` | `/api/webhooks/clerk` | Clerk svix signature | Sync users and orgs from Clerk lifecycle events |
| `POST` | `/api/webhooks/stripe` | Stripe raw-body signature | Sync subscription and plan changes from Stripe |
| `GET` | `/api/invoices/[id]/pdf` | Session (ADMIN+) | Generate invoice PDF via `@react-pdf/renderer`, store in Vercel Blob, return blob URL |
| `POST` | `/api/time-entries/[id]/stop` | Session (MEMBER+) | Stop an active timer by setting `stoppedAt = now()` |
| `GET` | `/api/cron/audit-prune` | `CRON_SECRET` header | Delete `audit_logs` older than plan retention window (30d/90d/365d) |
| `GET` | `/api/cron/invoice-overdue` | `CRON_SECRET` header | Set `SENT` invoices past `dueDate` to `OVERDUE` |

### Cron Handler Specifications

**`GET /api/cron/audit-prune`** — `app/api/cron/audit-prune/route.ts`
- Verify `Authorization: Bearer ${CRON_SECRET}` → return `401` if absent or wrong.
- For each org, look up `planTier` → retention days (STARTER: 30, PRO: 90, ENTERPRISE: 365).
- Execute: `DELETE FROM audit_logs WHERE org_id = $orgId AND created_at < NOW() - INTERVAL '$days days'`
- Return `200 { deleted: N }`.
- On DB error: return `500 { error: "db_unavailable" }` — Vercel Cron retries automatically.

**`GET /api/cron/invoice-overdue`** — `app/api/cron/invoice-overdue/route.ts`
- Verify `CRON_SECRET`.
- Execute: `UPDATE invoices SET status = 'OVERDUE', updated_at = NOW() WHERE status = 'SENT' AND due_date < NOW()`
- Return `200 { updated: N }`.
- On DB error: return `500 { error: "db_unavailable" }`.

### Webhook Handler Details

**`POST /api/webhooks/clerk`** — Svix header verification via `@clerk/nextjs/server`.
- `user.created` → upsert `User { clerkId, email, name }`
- `organization.created` → upsert `Organization { clerkOrgId, name, slug }`, create OWNER `Membership`, create `InvoiceSequence { orgId, lastSeq: 0 }`
- `organizationMembership.created` → create `Membership`
- `organizationMembership.updated` → update `Membership.role`
- `organizationMembership.deleted` → delete `Membership`

**`POST /api/webhooks/stripe`** — Raw body required; `stripe.webhooks.constructEvent(rawBody, sig, STRIPE_WEBHOOK_SECRET)`.
- `customer.subscription.created` → set `stripeSubscriptionId`, `stripePriceId`, `planTier`, `planSeats`, `currentPeriodEnd`
- `customer.subscription.updated` → sync same fields; on downgrade enforce plan limits (archive excess projects)
- `customer.subscription.deleted` → reset to `planTier: STARTER`, clear subscription fields
- `invoice.payment_succeeded` → update `currentPeriodEnd`
- `invoice.payment_failed` → write audit log entry, surface in-app notification to OWNER

---

## §6 — Error & Loading States

### `/dashboard`
- **Loading**: 4 stat-card skeletons, bar-chart skeleton, 3-row project list skeleton
- **Error**: "Could not load dashboard. Try refreshing." with retry button
- **Empty**: First-time welcome — guided steps: Create a project → Log time → Create invoice

### `/projects`
- **Loading**: 6-card grid skeleton
- **Error**: inline alert with retry
- **Empty**: `EmptyState` — "No projects yet" + "Create project" button (ADMIN+) or "Ask your admin to create a project" (VIEWER)

### `/projects/[id]`
- **Loading**: header skeleton + 5-row time table skeleton
- **Error**: 404 "Project not found" with back link
- **Empty (time entries)**: `EmptyState` — "No time logged yet" + "Log time" button

### `/clients`
- **Loading**: 4-card grid skeleton
- **Error**: inline alert with retry
- **Empty**: `EmptyState` — "No clients yet" + "Add client" button (ADMIN+)

### `/clients/[id]`
- **Loading**: header skeleton + stats skeleton + invoice list skeleton
- **Error**: 404 "Client not found"
- **Empty (invoices)**: `EmptyState` — "No invoices for this client"

### `/time`
- **Loading**: sticky timer bar skeleton + 7-row table skeleton
- **Error**: inline alert with retry
- **Empty**: `EmptyState` — "No time entries yet" + "Start timer" button

### `/invoices`
- **Loading**: status-tab skeleton + 5-row table skeleton
- **Error**: inline alert with retry
- **Empty**: `EmptyState` — "No invoices yet" + "Create invoice" button

### `/invoices/[id]`
- **Loading**: invoice header skeleton + line items skeleton
- **Error**: 404 "Invoice not found"
- **Empty (line items)**: `EmptyState` inside `LineItemEditor` — "Add your first line item"

### `/settings/general`
- **Loading**: form field skeletons (3 inputs + avatar upload)
- **Error**: inline alert with retry
- **Empty**: N/A (always populated from org data)

### `/settings/members`
- **Loading**: 3-row member table skeleton
- **Error**: inline alert with retry
- **Empty**: `EmptyState` — "Only you are here" + "Invite team members" button

### `/settings/billing`
- **Loading**: plan card skeleton + usage bar skeletons
- **Error**: inline alert — "Could not load billing info. Try again."
- **Empty**: N/A

### `/settings/audit`
- **Loading**: 10-row audit table skeleton
- **Error**: inline alert with retry
- **Empty**: `EmptyState` — "No activity recorded yet" (new org)

### Root Error Boundaries
- `app/error.tsx` — unhandled errors: "Something went wrong" + "Go to dashboard" link
- `app/global-error.tsx` — root layout errors (Clerk/DB init failures)
- `app/not-found.tsx` — 404 page with navigation back to dashboard

---

## §7 — Form Validation

### Project Form (`/projects/new`, `/projects/[id]/edit`)
| Field | Rules | Error Message |
|-------|-------|---------------|
| `name` | Required, 2–80 chars | "Project name is required" / "Max 80 characters" |
| `clientId` | Optional, valid UUID if set | "Select a valid client" |
| `hourlyRate` | Optional, positive decimal ≤ 99999.99 | "Enter a valid rate" |
| `budget` | Optional, positive decimal ≤ 999999.99 | "Enter a valid budget" |
| `color` | Required, valid hex | "Select a color" |

Submit button: disabled + spinner while Server Action is in-flight. On success: `router.push('/projects/[id]')`.

### Client Form (`/clients/new`, `/clients/[id]/edit`)
| Field | Rules | Error Message |
|-------|-------|---------------|
| `name` | Required, 2–100 chars | "Client name is required" |
| `email` | Optional, valid email | "Enter a valid email address" |
| `phone` | Optional, 6–20 chars | "Enter a valid phone number" |
| `address` | Optional, max 500 chars | "Max 500 characters" |

### Time Entry Form (`/time/new`, `/time/[id]/edit`)
| Field | Rules | Error Message |
|-------|-------|---------------|
| `projectId` | Required | "Select a project" |
| `startedAt` | Required, ISO datetime, not in the future | "Start time is required" / "Cannot start in the future" |
| `stoppedAt` | Optional, must be after `startedAt` | "Stop time must be after start time" |
| `durationMinutes` | Optional (used when `stoppedAt` is null), positive integer | "Enter duration in minutes" |
| `description` | Optional, max 500 chars | "Max 500 characters" |

If the user already has an active timer: show warning banner; starting a new timer auto-stops the previous one.

### Invoice Form — Step 1: Select Client
| Field | Rules | Error Message |
|-------|-------|---------------|
| `clientId` | Required | "Select a client" |
| `dueDate` | Required, today or future | "Due date must be in the future" |
| `currency` | Required, 3-letter ISO | "Select a currency" |

### Invoice Form — Step 2: Line Items (at least one required)
| Field | Rules | Error Message |
|-------|-------|---------------|
| `description` | Required, max 200 chars | "Description is required" |
| `quantity` | Required, positive decimal ≤ 9999.999 | "Enter a valid quantity" |
| `unitPrice` | Required, positive decimal ≤ 99999.99 | "Enter a valid price" |

"Import billable time" pre-populates line items from unbilled `TimeEntry` records for the selected client.

### Invite Member Form (`/settings/members`)
| Field | Rules | Error Message |
|-------|-------|---------------|
| `email` | Required, valid email | "Enter a valid email address" |
| `role` | Required, one of ADMIN / MEMBER / VIEWER | "Select a role" |

OWNER is excluded from the role selector — only the single OWNER can transfer ownership (separate explicit flow).

### Org Settings Form (`/settings/general`)
| Field | Rules | Error Message |
|-------|-------|---------------|
| `name` | Required, 2–80 chars | "Org name is required" |
| `slug` | Required, 3–30 chars, lowercase alphanumeric + hyphens, unique | "3–30 lowercase letters, numbers, or hyphens" / "Slug already taken" |
| `logoUrl` | Optional, Vercel Blob upload | — |

---

## §8 — Detailed Loading States (File Map)

Each page section has a `loading.tsx` at the route level. Settings sub-pages each have their own (recommended fix from review applied):

| File | Skeleton Content |
|------|-----------------|
| `app/(app)/dashboard/loading.tsx` | 4 stat-card skeletons, bar-chart, 3-row project list |
| `app/(app)/projects/loading.tsx` | 6-card grid |
| `app/(app)/projects/[id]/loading.tsx` | Header + 5-row time table |
| `app/(app)/clients/loading.tsx` | 4-card grid |
| `app/(app)/clients/[id]/loading.tsx` | Header + stats + invoice list |
| `app/(app)/time/loading.tsx` | Timer bar + 7-row table |
| `app/(app)/invoices/loading.tsx` | Tab nav + 5-row table |
| `app/(app)/invoices/[id]/loading.tsx` | Invoice header + line items |
| `app/(app)/settings/general/loading.tsx` | 3 input fields + avatar upload skeleton |
| `app/(app)/settings/members/loading.tsx` | 3-row member table |
| `app/(app)/settings/billing/loading.tsx` | Plan card + 2 usage bars |
| `app/(app)/settings/audit/loading.tsx` | 10-row audit table |

---

## §9 — Stripe Integration

### Plan Tiers
| Tier | Price | Active Projects | Seats | Audit Retention |
|------|-------|-----------------|-------|-----------------|
| STARTER | $29/mo | 3 | 3 | 30 days |
| PRO | $99/mo | 20 | 15 | 90 days |
| ENTERPRISE | $299/mo | Unlimited | Unlimited | 365 days |

### Subscription Flow
1. OWNER visits `/settings/billing` → clicks "Upgrade".
2. Server Action calls `stripe.checkout.sessions.create()` → redirect to Stripe Checkout.
3. On success Stripe fires `customer.subscription.created` → webhook handler updates org `planTier`.
4. "Manage Subscription" button opens Stripe Customer Portal (`stripe.billingPortal.sessions.create()`).

### Plan Limit Enforcement
- `create:project`: check `activeProjectCount < planLimit`. At limit → throw `PlanLimitError` → client renders `PlanGate` upgrade prompt.
- `invite:member`: check `memberCount < planSeats`. At limit → throw `PlanLimitError`.
- On downgrade: archive excess active projects (oldest first) to enforce new limit; data is never deleted.

---

## §10 — RBAC Capability Matrix

```typescript
// lib/rbac.ts

export type Role = 'OWNER' | 'ADMIN' | 'MEMBER' | 'VIEWER';

export type Action =
  | 'create:project' | 'update:project' | 'delete:project' | 'view:project'
  | 'create:client'  | 'update:client'  | 'delete:client'  | 'view:client'
  | 'create:time_entry' | 'update:time_entry' | 'delete:time_entry' | 'view:time_entry'
  | 'create:invoice' | 'update:invoice' | 'delete:invoice' | 'view:invoice'
  | 'manage:members' | 'manage:billing' | 'view:audit' | 'delete:org';

const CAPABILITIES: Record<Action, Role[]> = {
  // Projects
  'create:project':    ['OWNER', 'ADMIN'],
  'update:project':    ['OWNER', 'ADMIN'],
  'delete:project':    ['OWNER'],
  'view:project':      ['OWNER', 'ADMIN', 'MEMBER', 'VIEWER'],

  // Clients
  'create:client':     ['OWNER', 'ADMIN'],
  'update:client':     ['OWNER', 'ADMIN'],
  'delete:client':     ['OWNER'],
  'view:client':       ['OWNER', 'ADMIN', 'MEMBER', 'VIEWER'],

  // Time entries — after can() passes, enforce entry.userId === callerId for MEMBER (see §10 note)
  'create:time_entry': ['OWNER', 'ADMIN', 'MEMBER'],
  'update:time_entry': ['OWNER', 'ADMIN', 'MEMBER'],  // MEMBER: own entries only (row-level check in action)
  'delete:time_entry': ['OWNER', 'ADMIN'],
  'view:time_entry':   ['OWNER', 'ADMIN', 'MEMBER', 'VIEWER'],

  // Invoices — financial data; MEMBER excluded intentionally (billing staff only)
  'create:invoice':    ['OWNER', 'ADMIN'],
  'update:invoice':    ['OWNER', 'ADMIN'],
  'delete:invoice':    ['OWNER'],
  'view:invoice':      ['OWNER', 'ADMIN'],

  // Org management
  'manage:members':    ['OWNER', 'ADMIN'],
  'manage:billing':    ['OWNER'],
  'view:audit':        ['OWNER', 'ADMIN'],
  'delete:org':        ['OWNER'],
};

// Role hierarchy for route-level minimum-role guards
const ROLE_RANK: Record<Role, number> = {
  VIEWER: 0, MEMBER: 1, ADMIN: 2, OWNER: 3,
};

export function can(role: Role, action: Action): boolean {
  return CAPABILITIES[action].includes(role);
}

export function requireRole(userRole: Role, minRole: Role): boolean {
  return ROLE_RANK[userRole] >= ROLE_RANK[minRole];
}
```

> **MEMBER `update:time_entry` ownership enforcement** — In `lib/actions/time-actions.ts`, after `can(role, 'update:time_entry')` returns `true`, assert `entry.userId === callerId` when `role === 'MEMBER'`. Throw `AuthorizationError` if mismatched. ADMIN and OWNER may update any entry without this check. The `can()` function cannot enforce row-level ownership — this explicit assertion in the action is required.

---

## §11 — `tenantPrisma` Factory

```typescript
// lib/db/tenant-prisma.ts

import { PrismaClient } from '@prisma/client';

// Single global client instance — Prisma manages the connection pool.
const globalPrisma = new PrismaClient();

/**
 * Returns the Prisma client after setting the PostgreSQL session variable
 * `app.current_org_id` so RLS policies can call current_org_id().
 *
 * Every query MUST go through this factory — never expose globalPrisma
 * directly to route handlers or Server Actions.
 */
export async function tenantPrisma(orgId: string) {
  await globalPrisma.$executeRaw`SELECT set_config('app.current_org_id', ${orgId}, true)`;
  return globalPrisma;
}
```

The application layer always provides an explicit `orgId` filter on every query — `tenantPrisma` sets the session variable as a second enforcement layer for RLS.

---

## §12 — Key File Structure

```
app/
├── error.tsx                               # Root error boundary
├── global-error.tsx                        # Root layout error (Clerk/DB init failures)
├── not-found.tsx                           # 404 page
├── layout.tsx                              # ClerkProvider, ThemeProvider
│
├── (marketing)/
│   └── page.tsx                            # Landing page (/)
│
├── (auth)/
│   ├── sign-in/[[...sign-in]]/page.tsx
│   └── sign-up/[[...sign-up]]/page.tsx
│
├── onboarding/
│   └── page.tsx                            # Create org or accept invite
│
└── (app)/
    ├── layout.tsx                          # AppShell (auth + org context)
    ├── dashboard/
    │   ├── loading.tsx
    │   └── page.tsx
    ├── projects/
    │   ├── loading.tsx
    │   ├── page.tsx
    │   ├── new/page.tsx
    │   └── [id]/
    │       ├── loading.tsx
    │       ├── page.tsx
    │       └── edit/page.tsx
    ├── clients/
    │   ├── loading.tsx
    │   ├── page.tsx
    │   ├── new/page.tsx
    │   └── [id]/
    │       ├── loading.tsx
    │       ├── page.tsx
    │       └── edit/page.tsx
    ├── time/
    │   ├── loading.tsx
    │   ├── page.tsx
    │   ├── new/page.tsx
    │   └── [id]/edit/page.tsx
    ├── invoices/
    │   ├── loading.tsx
    │   ├── page.tsx
    │   ├── new/page.tsx
    │   └── [id]/
    │       ├── loading.tsx
    │       ├── page.tsx
    │       └── edit/page.tsx
    └── settings/
        ├── page.tsx                        # Role-aware redirect (OWNER→general, ADMIN→members)
        ├── general/
        │   ├── loading.tsx
        │   └── page.tsx
        ├── members/
        │   ├── loading.tsx
        │   └── page.tsx
        ├── billing/
        │   ├── loading.tsx
        │   └── page.tsx
        └── audit/
            ├── loading.tsx
            └── page.tsx

app/api/
├── webhooks/
│   ├── clerk/route.ts                      # Svix signature verification
│   └── stripe/route.ts                     # Raw body + constructEvent()
├── invoices/
│   └── [id]/pdf/route.ts                   # PDF generation → Vercel Blob
├── time-entries/
│   └── [id]/stop/route.ts                  # Stop active timer
└── cron/
    ├── audit-prune/route.ts                # DELETE expired audit_logs (CRON_SECRET)
    └── invoice-overdue/route.ts            # UPDATE SENT→OVERDUE past dueDate (CRON_SECRET)

lib/
├── db/
│   └── tenant-prisma.ts                    # tenantPrisma(orgId) factory
├── rbac.ts                                 # can(), requireRole(), CAPABILITIES
├── actions/
│   ├── project-actions.ts
│   ├── client-actions.ts
│   ├── time-actions.ts                     # includes MEMBER ownership assertion
│   └── invoice-actions.ts
├── services/
│   ├── invoice-service.ts                  # sequencing (SELECT FOR UPDATE), PDF generation
│   ├── stripe-service.ts                   # checkout + portal session creation
│   └── audit-service.ts                   # writeAuditLog called via after()
└── utils/
    ├── plan-limits.ts                      # requirePlan(), getPlanLimits()
    └── invoice-number.ts                   # formatInvoiceNumber(seq, year)

components/
├── layout/                                 # AppShell, Sidebar, TopBar, OrgSwitcher, PlanBanner
├── projects/                               # ProjectCard, ProjectList, ProjectForm, ProjectBudgetBar
├── clients/                                # ClientCard, ClientForm
├── time/                                   # TimerWidget, TimeEntryRow, TimeEntryTable, TimeEntryForm, DailyTotalBar
├── invoices/                               # InvoiceStatusBadge, InvoiceList, InvoiceForm, LineItemEditor, InvoicePreview, InvoiceActions
├── settings/                               # MemberTable, InviteForm, BillingCard, AuditLogTable, AuditLogFilters, DangerZone
└── ui/                                     # PageHeader, EmptyState, DataTable, ConfirmDialog, StatusSelect,
                                            # CurrencyInput, DurationInput, DateRangePicker, RoleBadge, PlanGate, RoleGate

prisma/
├── schema.prisma
└── migrations/
    └── YYYYMMDD_partial_unique_timer/
        └── migration.sql                   # Partial unique index + RLS setup

proxy.ts                                    # clerkMiddleware, RBAC route guards, header injection
vercel.ts                                   # Cron schedule configuration
```

---

## §13 — Environment Variables

| Variable | Source | Notes |
|----------|--------|-------|
| `DATABASE_URL` | Neon (Vercel Marketplace, auto-provisioned) | Pooled connection for runtime |
| `DIRECT_URL` | Neon (Vercel Marketplace, auto-provisioned) | Direct connection for Prisma migrations |
| `CLERK_SECRET_KEY` | Clerk (Vercel Marketplace, auto-provisioned) | Server-side Clerk SDK |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk (Vercel Marketplace, auto-provisioned) | Client-side Clerk |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | Set manually | Value: `/sign-in` — required to avoid Clerk redirect loop |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | Set manually | Value: `/sign-up` — required to avoid Clerk redirect loop |
| `CLERK_WEBHOOK_SECRET` | Clerk dashboard (Svix) | Webhook signature verification |
| `STRIPE_SECRET_KEY` | Stripe dashboard | Server-side Stripe SDK |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe dashboard | Client-side Stripe.js |
| `STRIPE_WEBHOOK_SECRET` | Stripe dashboard | `stripe.webhooks.constructEvent()` raw-body signing |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob dashboard | Invoice PDF storage |
| `CRON_SECRET` | `openssl rand -base64 32` | Shared secret for cron route auth; sent by Vercel Cron automatically |

---

## §14 — `vercel.ts` Configuration

```typescript
// vercel.ts
import { type VercelConfig } from '@vercel/config/v1';

export const config: VercelConfig = {
  framework: 'nextjs',
  crons: [
    {
      path: '/api/cron/audit-prune',
      schedule: '0 2 * * *',    // 02:00 UTC nightly — prune expired audit logs
    },
    {
      path: '/api/cron/invoice-overdue',
      schedule: '0 6 * * *',    // 06:00 UTC daily — mark overdue invoices
    },
  ],
};
```

Cron handlers (`app/api/cron/audit-prune/route.ts`, `app/api/cron/invoice-overdue/route.ts`) verify `Authorization: Bearer ${CRON_SECRET}` and return `401` if missing or incorrect. Vercel Cron sends this header automatically when `CRON_SECRET` is set as an environment variable on the project.

---

## §15 — Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| MEMBER excluded from `view:invoice` | MEMBERs are time-entry workers, not billing staff. Keeping financial data (amounts, rates, client billing details) away from MEMBER role matches professional-services norms. A MEMBER needing invoice access should have their role upgraded to ADMIN. |
| `/settings` role-aware redirect | Prevents the authorization dead-end. OWNER → `/settings/general` (org config + danger zone). ADMIN → `/settings/members` (their primary settings task). No ADMIN ever reaches OWNER-only pages. |
| `tenantPrisma` + RLS double enforcement | Defense-in-depth: app layer filters by `orgId` on every query; RLS catches developer errors at the DB layer. Two independent checks — neither alone is sufficient for a multi-tenant SaaS. |
| Cron routes in `app/api/cron/` | Standard Next.js Route Handler location, clearly separated from user-facing API. `CRON_SECRET` prevents unauthenticated execution. Vercel Cron sends the secret automatically when it is set as an environment variable. |
| `SECURITY DEFINER current_org_id()` | Breaks the circular RLS dependency pattern. The function reads only a PostgreSQL session variable — it does not query any RLS-protected table — so there is no risk of infinite recursion or silent empty results. |
| Invoice sequence via `SELECT FOR UPDATE` | Prevents race conditions from concurrent invoice creation generating duplicate numbers. The `InvoiceSequence` table is a lightweight per-org counter. |
| Audit writes via `after()` | Post-response execution ensures audit writes never add latency to user-facing mutations. Acceptable trade-off: a crash after response but before write could theoretically lose one event (extremely rare in practice). |
| PDF via Route Handler → Vercel Blob | Keeps PDF generation off the mutation path. Triggered explicitly; Blob URL stored on the invoice. Subsequent downloads are direct Blob fetches — no regeneration on every view. |
